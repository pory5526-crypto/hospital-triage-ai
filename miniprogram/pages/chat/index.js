const { requestJSON, uploadFile, uploadAudio, streamChat } = require('../../utils/http');

const uid = () => Math.random().toString(36).slice(2, 10);

const REASON_TEXT = {
  user_request: '您主动要求人工协助',
  out_of_scope: '问题超出导诊范围',
  fail_streak: '连续未识别您的问题',
};

Page({
  data: {
    statusBarHeight: 20,
    navTotal: 64,
    hospital: '',
    subtitle: '',
    entries: [],
    quickActions: [],
    messages: [],
    dayLabel: '',
    pending: false,
    showTyping: false,
    inputValue: '',
    canSend: false,
    keyboardHeight: 0,
    toastText: '',
    showHandoff: false,
    handoff: {},
    showAttach: false,
    maxUploadMb: 10,
    recording: false,
  },

  streamIndex: -1,
  lastScrollAt: 0,
  toastTimer: null,

  onLoad() {
    const app = getApp();
    const statusBarHeight = app.globalData.statusBarHeight || 20;
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');

    this.setData({
      statusBarHeight,
      navTotal: statusBarHeight + 44,
      dayLabel: '今天 ' + hh + ':' + mm,
    });

    this.loadConfig();
    this.initRecorder();

    // 键盘弹出时把输入框顶上去（固定定位元素不会自动避让）
    if (wx.onKeyboardHeightChange) {
      wx.onKeyboardHeightChange((res) => {
        this.setData({ keyboardHeight: res.height > 0 ? res.height : 0 });
        if (res.height > 0) this.scrollToBottom(true);
      });
    }
  },

  onUnload() {
    if (this.toastTimer) clearTimeout(this.toastTimer);
    if (wx.offKeyboardHeightChange) wx.offKeyboardHeightChange();
    if (this.recorder && this.data.recording) {
      this.recordStarted = false;
      this.recorder.stop();
    }
  },

  // ---------------------------------------------------------------- 初始化
  loadConfig() {
    requestJSON('GET', '/api/config')
      .then((cfg) => {
        this.config = cfg;
        this.setData({
          hospital: cfg.hospital.name,
          subtitle: cfg.welcome.subtitle,
          entries: cfg.entries,
          quickActions: cfg.quickActions,
          maxUploadMb: cfg.upload.maxMb,
          messages: [
            {
              id: 'welcome',
              role: 'assistant',
              text: cfg.welcome.text,
              chips: cfg.welcome.chips || [],
              streaming: false,
            },
          ],
        });
      })
      .catch((err) => {
        this.toast('连接医院服务失败：' + err.message);
        this.setData({
          hospital: '协和医院',
          subtitle: '智能分诊客服，7×24 小时在线',
          entries: ['症状自查', '科室推荐', '预约挂号', '报告解读'],
          quickActions: ['转人工客服', '报告解读', '复诊提醒'],
          messages: [
            {
              id: 'welcome',
              role: 'assistant',
              text: '您好，我是智能导诊助手小医助。请用一两句话描述哪里不舒服、持续多久了，我帮您判断该挂哪个科室。',
              chips: ['头晕心慌', '头痛发热', '腹痛腹泻', '咳嗽咽痛'],
              streaming: false,
            },
          ],
        });
      });
  },

  // ---------------------------------------------------------------- 发送
  send(text, opts) {
    opts = opts || {};
    if (this.data.pending) return;

    const shownRaw = opts.displayText !== undefined ? opts.displayText : text || '';
    const shown = String(shownRaw).trim();
    if (!shown && !opts.fileName) return;

    const userMsg = {
      id: uid(),
      role: 'user',
      text: shown,
      chips: [],
      fileName: opts.fileName || '',
      fileExt: opts.fileName ? String(opts.fileName).split('.').pop().slice(0, 4).toUpperCase() : '',
    };

    this.streamIndex = -1;
    this.setData({
      messages: this.data.messages.concat([userMsg]),
      pending: true,
      showTyping: true,
      inputValue: '',
      canSend: false,
    });
    this.scrollToBottom(true);

    const app = getApp();

    streamChat({
      sessionId: app.globalData.sessionId,
      message: text || '',
      imageText: opts.imageText || '',
      fileName: opts.fileName || '',
      onEvent: (event) => this.handleEvent(event),
      onComplete: () => this.finish(),
      onError: (err) => {
        this.setData({
          messages: this.data.messages.concat([
            {
              id: uid(),
              role: 'assistant',
              text: '连接失败：' + (err.message || '网络异常') + '。请检查网络后重试，或点击下方「转人工客服」。',
              chips: [],
            },
          ]),
        });
        this.toast('回复失败，可重试');
        this.finish();
      },
    });
  },

  handleEvent(event) {
    const app = getApp();

    switch (event.type) {
      case 'meta':
        app.globalData.sessionId = event.sessionId;
        break;

      case 'delta': {
        const i = this.ensureAssistant();
        const cur = this.data.messages[i];
        const patch = { ['messages[' + i + '].text']: (cur.text || '') + event.text };
        // 第一个字到了就收起「正在输入」的三个点
        if (this.data.showTyping) patch.showTyping = false;
        this.setData(patch);
        this.scrollToBottom();
        break;
      }

      case 'card': {
        const i = this.ensureAssistant();
        this.setData({ ['messages[' + i + '].card']: event.card });
        if (event.card.type === 'triage') {
          app.globalData.lastTriage = {
            dept: event.card.primary.dept,
            location: event.card.primary.location,
          };
        }
        this.scrollToBottom(true);
        break;
      }

      case 'segment_end': {
        if (this.streamIndex >= 0) {
          this.setData({ ['messages[' + this.streamIndex + '].streaming']: false });
        }
        this.streamIndex = -1;
        break;
      }

      case 'handoff':
        this.openHandoff(event.handoff);
        break;

      case 'error':
        if (!event.silent) this.toast(event.message);
        break;

      default:
        break;
    }
  },

  ensureAssistant() {
    if (this.streamIndex >= 0) return this.streamIndex;
    const idx = this.data.messages.length;
    this.streamIndex = idx;
    this.setData({
      messages: this.data.messages.concat([
        { id: uid(), role: 'assistant', text: '', chips: [], streaming: true },
      ]),
    });
    return idx;
  },

  finish() {
    if (this.streamIndex >= 0) {
      this.setData({ ['messages[' + this.streamIndex + '].streaming']: false });
    }
    this.streamIndex = -1;
    this.setData({ pending: false, showTyping: false });
    this.scrollToBottom(true);
  },

  scrollToBottom(force) {
    const now = Date.now();
    if (!force && now - this.lastScrollAt < 180) return;
    this.lastScrollAt = now;
    wx.pageScrollTo({ scrollTop: 999999, duration: force ? 200 : 0 });
  },

  // ---------------------------------------------------------------- 交互
  onInput(e) {
    const value = e.detail.value;
    this.setData({ inputValue: value, canSend: !!value.trim() });
  },

  onInputFocus() {
    setTimeout(() => this.scrollToBottom(true), 260);
  },

  onSendTap() {
    const text = (this.data.inputValue || '').trim();
    if (!text) return;
    this.send(text);
  },

  onChip(e) {
    const chip = e.currentTarget.dataset.chip;
    this.send(chip);
  },

  onEntry() {
    this.toast('功能即将上线，敬请期待');
  },

  onQuick(e) {
    const action = e.currentTarget.dataset.action;
    if (action === '转人工客服') {
      const cfg = this.config || { hospital: {} };
      this.openHandoff({
        reason: 'user_request',
        phone: (cfg.hospital && cfg.hospital.triagePhone) || '010-69156114',
        hours: (cfg.hospital && cfg.hospital.serviceHours) || '工作日 7:30–17:00',
        afterHoursTip: (cfg.hospital && cfg.hospital.afterHoursTip) || '',
        title: '联系人工导诊',
      });
      return;
    }
    this.toast('功能即将上线，敬请期待');
  },

  onViewFlow(e) {
    const ds = e.currentTarget.dataset;
    wx.navigateTo({
      url:
        '/pages/flow/index?dept=' +
        encodeURIComponent(ds.dept || '心血管内科') +
        '&location=' +
        encodeURIComponent(ds.loc || '门诊楼 3F · A 区'),
    });
  },

  onBack() {
    wx.navigateBack({
      delta: 1,
      fail() {
        // 已经是首个页面，忽略
      },
    });
  },

  // ---------------------------------------------------------------- 语音
  initRecorder() {
    this.recordStarted = false;
    this.recorder = wx.getRecorderManager();

    this.recorder.onStop((res) => {
      if (!this.recordStarted) return;
      this.recordStarted = false;
      this.setData({ recording: false });
      if (!res || !res.tempFilePath) {
        this.toast('没有录到声音，请再说一次');
        return;
      }
      wx.showLoading({ title: '识别中…', mask: true });
      uploadAudio(res.tempFilePath)
        .then((body) => {
          wx.hideLoading();
          if (!body || !body.ok) {
            this.toast((body && body.error) || '没听清，请再说一次');
            return;
          }
          this.send(body.text);
        })
        .catch((err) => {
          wx.hideLoading();
          this.toast(err.message || '语音识别失败');
        });
    });

    this.recorder.onError(() => {
      this.recordStarted = false;
      this.setData({ recording: false });
      this.toast('录音失败，请检查麦克风权限');
    });
  },

  onVoice() {
    if (this.data.recording) {
      this.recorder.stop();
      return;
    }
    if (this.data.pending) {
      this.toast('正在等回复，稍等一下');
      return;
    }
    this.startVoice();
  },

  startVoice() {
    const begin = () => {
      this.recordStarted = true;
      this.setData({ recording: true });
      this.recorder.start({
        duration: 60000,
        sampleRate: 16000,
        numberOfChannels: 1,
        encodeBitRate: 48000,
        format: 'mp3',
      });
    };

    wx.authorize({
      scope: 'scope.record',
      success: begin,
      fail: () =>
        wx.showModal({
          title: '需要麦克风权限',
          content: '请在设置里允许使用麦克风，或者改用文字描述症状。',
          confirmText: '去设置',
          success: (res) => {
            if (res.confirm) wx.openSetting();
          },
        }),
    });
  },

  noop() {},

  // ---------------------------------------------------------------- 弹窗
  openHandoff(info) {
    const reasonText = REASON_TEXT[info.reason] || '系统建议转人工';
    this.setData({
      showHandoff: true,
      handoff: {
        title: info.title || '联系人工导诊',
        phone: info.phone,
        hours: info.hours,
        afterHoursTip: info.afterHoursTip,
        reason: info.reason,
        reasonText,
      },
    });
  },

  closeHandoff() {
    this.setData({ showHandoff: false });
  },

  onCallHandoff(e) {
    const phone = e.currentTarget.dataset.phone;
    wx.makePhoneCall({ phoneNumber: String(phone).replace(/[^\d]/g, '') });
  },

  onCallEmergency(e) {
    const phone = e.currentTarget.dataset.phone;
    wx.makePhoneCall({ phoneNumber: String(phone).replace(/[^\d]/g, '') });
  },

  onAttach() {
    this.setData({ showAttach: true });
  },

  closeAttach() {
    this.setData({ showAttach: false });
  },

  // ---------------------------------------------------------------- 文件
  chooseImage() {
    this.setData({ showAttach: false });
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (file) this.handleFile(file.tempFilePath, '图片病历.png');
      },
      fail: () => {},
    });
  },

  chooseDoc() {
    this.setData({ showAttach: false });
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['pdf', 'docx'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (file) this.handleFile(file.path, file.name);
      },
      fail: () => {},
    });
  },

  handleFile(filePath, name) {
    const app = getApp();
    const maxMb = this.data.maxUploadMb || 10;
    this.toast('正在识别文件内容…');

    wx.getFileInfo({
      filePath,
      success: (info) => {
        if (info.size > maxMb * 1024 * 1024) {
          this.toast('文件超过 ' + maxMb + 'MB，请压缩后重试');
          return;
        }
        this.doUpload(filePath, name);
      },
      fail: () => this.doUpload(filePath, name),
    });
  },

  doUpload(filePath, name) {
    const app = getApp();
    uploadFile(filePath, name, app.globalData.sessionId)
      .then((res) => {
        if (!res.ok) {
          this.toast(res.error || '文件识别失败，请重新上传');
          return;
        }
        this.send('', {
          imageText: res.text,
          fileName: res.fileName || name,
          displayText: '',
        });
      })
      .catch((err) => this.toast(err.message || '上传失败，请重试'));
  },

  // ---------------------------------------------------------------- Toast
  noop() {},

  toast(text) {
    if (!text) return;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.setData({ toastText: text });
    this.toastTimer = setTimeout(() => this.setData({ toastText: '' }), 2800);
  },
});

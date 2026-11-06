const STEPS = [
  {
    title: '在线预问诊',
    desc: '已提交症状描述，生成初步分诊建议，用时 3 分钟。',
    state: 'done',
    where: '',
  },
  {
    title: '预约挂号',
    desc: '选择就诊时段并支付挂号费，医保可直接线上结算。',
    state: 'now',
    where: '小程序 · 本次预约',
  },
  {
    title: '到院签到',
    desc: '到院后扫导诊屏二维码签到，或在自助机刷身份证取号。',
    state: 'todo',
    where: '门诊楼 1F 导诊台',
  },
  {
    title: '候诊叫号',
    desc: '在候诊区等候，叫号会同步推送到微信服务通知。',
    state: 'todo',
    where: '',
  },
  {
    title: '医生就诊',
    desc: '携带既往病历与检查报告进入诊室，向医生说明症状的具体时间。',
    state: 'todo',
    where: '3 号诊室',
  },
  {
    title: '检查与取药',
    desc: '如需抽血或心电图，按医嘱前往检查区；处方可在门诊药房窗口或线上取药。',
    state: 'todo',
    where: '',
  },
  {
    title: '复诊提醒',
    desc: '检查结果出来后，可在微信里收到复诊提醒并续约。',
    state: 'todo',
    where: '',
  },
];

const TIPS = [
  '身份证、医保卡（电子医保凭证同样有效）',
  '近期检查报告、正在服用的药物清单',
  '建议提前 15 分钟到院，空腹项目请勿进食',
];

Page({
  data: {
    statusBarHeight: 20,
    navTotal: 64,
    dept: '心血管内科',
    location: '门诊楼 3F · A 区',
    steps: STEPS,
    tips: TIPS,
  },

  onLoad(query) {
    const app = getApp();
    const statusBarHeight = app.globalData.statusBarHeight || 20;
    const dept = query.dept ? decodeURIComponent(query.dept) : '心血管内科';
    const location = query.location ? decodeURIComponent(query.location) : '门诊楼 3F · A 区';

    this.setData({
      statusBarHeight,
      navTotal: statusBarHeight + 44,
      dept,
      location,
    });

    wx.setNavigationBarTitle({ title: '就诊流程' });
  },

  onBack() {
    wx.navigateBack({ delta: 1 });
  },

  onAppointment() {
    wx.showToast({
      title: '线上挂号即将上线，可前往导诊台/自助机挂号',
      icon: 'none',
      duration: 2600,
    });
  },
});

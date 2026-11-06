import { useCallback, useEffect, useRef, useState } from 'react';
import { Capsule, StatusBar } from './components/StatusBar';
import { ChatPage } from './components/ChatPage';
import { FlowPage, type FlowDept } from './components/FlowPage';
import { HandoffSheet } from './components/HandoffSheet';
import { AttachSheet } from './components/AttachSheet';
import { useChat } from './hooks/useChat';
import { getConfig, uploadFile } from './lib/api';
import type { ClientConfig, HandoffInfo } from './lib/types';
import './styles/app.css';

export default function App() {
  const [config, setConfig] = useState<ClientConfig | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [page, setPage] = useState<'chat' | 'flow'>('chat');
  const [flowDept, setFlowDept] = useState<FlowDept>({ name: '心血管内科', location: '门诊楼 3F · A 区' });
  const [handoff, setHandoff] = useState<HandoffInfo | null>(null);
  const [attachOpen, setAttachOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((text: string) => {
    setToast(text);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const chat = useChat({ onHandoff: setHandoff, onToast: showToast });
  const seed = chat.seed;

  const load = useCallback(() => {
    setLoadError(null);
    getConfig()
      .then((cfg) => {
        setConfig(cfg);
        seed(cfg.welcome.text, cfg.welcome.chips);
      })
      .catch((err: Error) => setLoadError(err.message));
  }, [seed]);

  useEffect(() => {
    load();
  }, [load]);

  // 演示/截图用：?view=flow|handoff|attach 直接打开对应界面
  useEffect(() => {
    const view = new URLSearchParams(window.location.search).get('view');
    if (view === 'flow') setPage('flow');
    if (view === 'attach') setAttachOpen(true);
    if (view === 'handoff') {
      setHandoff({
        reason: 'user_request',
        phone: '010-69156114',
        hours: '工作日 7:30–17:00 · 周六 8:00–12:00',
        afterHoursTip: '非人工服务时间请前往门诊楼 1F 导诊台，急诊请直接到急诊楼 1F。',
        title: '联系人工导诊',
      });
    }
  }, []);

  // 演示/截图用：?q=xxx 打开即自动发一条消息
  const sendRef = useRef(chat.send);
  sendRef.current = chat.send;
  useEffect(() => {
    if (!config) return;
    const q = new URLSearchParams(window.location.search).get('q');
    if (!q) return;
    const timer = window.setTimeout(() => void sendRef.current(q), 400);
    return () => window.clearTimeout(timer);
  }, [config]);

  const defaultHandoff: HandoffInfo = {
    reason: 'user_request',
    phone: config?.hospital.triagePhone ?? '010-69156114',
    hours: config?.hospital.serviceHours ?? '工作日 7:30–17:00',
    afterHoursTip: config?.hospital.afterHoursTip ?? '',
    title: '联系人工导诊',
  };

  const handleQuickAction = (action: string) => {
    if (action === '转人工客服') {
      setHandoff(defaultHandoff);
      return;
    }
    showToast('功能即将上线，敬请期待');
  };

  const handleFile = async (file: File) => {
    const maxMb = config?.upload.maxMb ?? 10;
    if (file.size > maxMb * 1024 * 1024) {
      showToast(`文件超过 ${maxMb}MB，请压缩后重试`);
      return;
    }
    showToast('正在识别文件内容…');
    try {
      const result = await uploadFile(file, chat.sessionId ?? '');
      if (!result.ok) {
        showToast(result.error ?? '文件识别失败，请重新上传');
        return;
      }
      await chat.send('', {
        imageText: result.text,
        fileName: result.fileName,
        file: { name: result.fileName },
        displayText: '',
      });
    } catch (err) {
      showToast(err instanceof Error ? err.message : '上传失败，请重试');
    }
  };

  if (loadError) {
    return (
      <div className="app-shell">
        <div className="device">
          <div className="screen">
            <div style={{ margin: 'auto', padding: 32, textAlign: 'center' }}>
              <p style={{ fontSize: 14, color: '#42606A' }}>服务连接失败：{loadError}</p>
              <button className="btn primary" style={{ marginTop: 16 }} onClick={load} type="button">
                重新连接
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="app-shell">
        <div className="device">
          <div className="screen">
            <div style={{ margin: 'auto', color: '#8CA2AA', fontSize: 13 }}>正在连接医院服务…</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="device">
        <div className="screen">
          <StatusBar />
          <Capsule />

          {page === 'chat' ? (
            <ChatPage
              config={config}
              messages={chat.messages}
              pending={chat.pending}
              sessionId={chat.sessionId}
              onSend={(text) => void chat.send(text)}
              onQuickAction={handleQuickAction}
              onEntry={() => showToast('功能即将上线，敬请期待')}
              onAttach={() => setAttachOpen(true)}
              onOpenFlow={(dept) => {
                setFlowDept(dept);
                setPage('flow');
              }}
              toast={showToast}
              onVoiceStart={() => undefined}
            />
          ) : (
            <FlowPage
              dept={flowDept}
              onBack={() => setPage('chat')}
              onAppointment={() => showToast('线上挂号即将上线，可前往导诊台/自助机挂号')}
            />
          )}

          {attachOpen && (
            <AttachSheet
              accept={config.upload.accept}
              maxMb={config.upload.maxMb}
              onFile={(file) => void handleFile(file)}
              onClose={() => setAttachOpen(false)}
            />
          )}

          {handoff && (
            <HandoffSheet
              info={handoff}
              hospitalName={config.hospital.name}
              onClose={() => setHandoff(null)}
            />
          )}

          {toast && <div className="toast">{toast}</div>}
        </div>
      </div>
      <div className="desk-note">微信小程序预览 · 375 × 812 · 手机端自动全屏</div>
    </div>
  );
}

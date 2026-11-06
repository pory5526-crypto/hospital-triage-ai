import { useEffect, useRef } from 'react';
import { NavBar } from './NavBar';
import { WelcomeCard } from './WelcomeCard';
import { TriageCard } from './TriageCard';
import { EmergencyCard } from './EmergencyCard';
import { Composer } from './Composer';
import type { ChatMessage, ClientConfig } from '../lib/types';
import type { FlowDept } from './FlowPage';

interface Props {
  config: ClientConfig;
  messages: ChatMessage[];
  pending: boolean;
  sessionId?: string;
  onSend: (text: string) => void;
  onQuickAction: (action: string) => void;
  onEntry: (name: string) => void;
  onAttach: () => void;
  onOpenFlow: (dept: FlowDept) => void;
  toast: (text: string) => void;
  onVoiceStart: () => void;
}

function FileBubble({ name }: { name: string }) {
  const ext = name.split('.').pop()?.toUpperCase() ?? 'FILE';
  return (
    <div className="file-bubble">
      <span className="ficon">{ext.slice(0, 4)}</span>
      <span className="fmeta">
        <span className="fname">{name}</span>
        <span className="fstat">已上传 · 正在识别内容</span>
      </span>
    </div>
  );
}

export function ChatPage({
  config,
  messages,
  pending,
  sessionId,
  onSend,
  onQuickAction,
  onEntry,
  onAttach,
  onOpenFlow,
  toast,
  onVoiceStart,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const dayRef = useRef(
    `今天 ${String(new Date().getHours()).padStart(2, '0')}:${String(new Date().getMinutes()).padStart(2, '0')}`,
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages, pending]);

  const last = messages[messages.length - 1];
  const showTyping = pending && (!last || last.role === 'user');

  return (
    <>
      <NavBar title="智能导诊" showOnline />

      <div className="content" ref={scrollRef}>
        <WelcomeCard
          hospital={config.hospital.name}
          subtitle={config.welcome.subtitle}
          entries={config.entries}
          onEntry={onEntry}
        />

        <div className="day">{dayRef.current}</div>

        {messages.map((message) => {
          if (message.role === 'user') {
            return (
              <div className="row me" key={message.id}>
                {message.file ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                    <FileBubble name={message.file.name} />
                    {message.text && <div className="bubble">{message.text}</div>}
                  </div>
                ) : (
                  <div className="bubble">{message.text}</div>
                )}
              </div>
            );
          }

          return (
            <div key={message.id}>
              {(message.text || message.chips) && (
                <div className="row">
                  <div className="mini-av">医</div>
                  <div className="bubble">
                    {message.text}
                    {message.streaming && <span className="caret" />}
                    {message.chips && message.chips.length > 0 && (
                      <div className="chips">
                        {message.chips.map((chip) => (
                          <button className="chip" key={chip} onClick={() => onSend(chip)} type="button">
                            {chip}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {message.card?.type === 'triage' && (
                <TriageCard
                  card={message.card}
                  showChangeDept={false}
                  onViewFlow={() =>
                    onOpenFlow({
                      name: message.card && message.card.type === 'triage'
                        ? message.card.primary.dept
                        : '心血管内科',
                      location:
                        (message.card?.type === 'triage' && message.card.primary.location) ||
                        '门诊楼 3F · A 区',
                    })
                  }
                />
              )}

              {message.card?.type === 'emergency' && (
                <EmergencyCard
                  card={message.card}
                  onCall={() => {
                    window.location.href = `tel:${message.card && message.card.type === 'emergency' ? message.card.phone : ''}`;
                  }}
                />
              )}
            </div>
          );
        })}

        {showTyping && (
          <div className="row">
            <div className="mini-av">医</div>
            <div className="bubble" style={{ padding: 0 }}>
              <div className="typing">
                <i />
                <i />
                <i />
              </div>
            </div>
          </div>
        )}
      </div>

      <Composer
        quickActions={config.quickActions}
        pending={pending}
        sessionId={sessionId}
        onSend={onSend}
        onQuick={onQuickAction}
        onAttach={onAttach}
        onVoiceStart={onVoiceStart}
        toast={toast}
      />
      <div className="homebar">
        <i />
      </div>
    </>
  );
}

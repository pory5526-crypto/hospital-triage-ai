import { useRef, useState } from 'react';
import { useSpeech } from '../hooks/useSpeech';

interface Props {
  quickActions: string[];
  pending: boolean;
  sessionId?: string;
  placeholder?: string;
  onSend: (text: string) => void;
  onQuick: (name: string) => void;
  onAttach: () => void;
  onVoiceStart?: () => void;
  toast: (text: string) => void;
}

export function Composer({
  quickActions,
  pending,
  sessionId,
  placeholder = '描述您的症状，如：头晕、心慌…',
  onSend,
  onQuick,
  onAttach,
  onVoiceStart,
  toast,
}: Props) {
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const speech = useSpeech({
    sessionId,
    onFinal: (text) => {
      if (text.trim()) onSend(text.trim());
    },
    onError: (message) => toast(message),
  });

  const submit = () => {
    const text = value.trim();
    if (!text || pending) return;
    setValue('');
    onSend(text);
  };

  const toggleVoice = () => {
    if (speech.transcribing) {
      toast('正在识别刚才的录音…');
      return;
    }
    if (speech.listening) {
      speech.stop();
      return;
    }
    onVoiceStart?.();
    void speech.start();
  };

  return (
    <div className="dock">
      <div className="quick">
        {quickActions.map((action) => (
          <button key={action} onClick={() => onQuick(action)} type="button">
            {action === '转人工客服' && (
              <svg viewBox="0 0 24 24">
                <path d="M4 12a8 8 0 1 1 8 8H4v-4" />
              </svg>
            )}
            {action === '报告解读' && (
              <svg viewBox="0 0 24 24">
                <path d="M6 3.5h8L19 8v12.5H6z" />
              </svg>
            )}
            {action === '复诊提醒' && (
              <svg viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="8.5" />
                <path d="M12 7.5V12l3 2" />
              </svg>
            )}
            {action}
          </button>
        ))}
      </div>

      <div className="inputbar">
        <button
          className={`ibtn ${speech.listening ? 'active' : ''}`}
          onClick={toggleVoice}
          title="语音输入"
          type="button"
        >
          <svg viewBox="0 0 24 24">
            <rect height="10" rx="3" width="6" x="9" y="3" />
            <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" />
          </svg>
        </button>

        {speech.listening ? (
          <div className="recording" onClick={() => speech.stop()}>
            <span className="wave">
              <i />
              <i />
              <i />
              <i />
              <i />
            </span>
            正在录音 {speech.elapsed}s · 点这里结束
          </div>
        ) : speech.transcribing ? (
          <div className="recording transcribing">
            <span className="wave">
              <i />
              <i />
              <i />
              <i />
              <i />
            </span>
            识别中…
          </div>
        ) : (
          <div className="field">
            <input
              ref={inputRef}
              value={value}
              placeholder={placeholder}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  submit();
                }
              }}
            />
          </div>
        )}

        <button className="ibtn" onClick={onAttach} title="上传病历/检查单" type="button">
          <svg viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="8.5" />
            <path d="M12 8.2v7.6M8.2 12h7.6" />
          </svg>
        </button>

        <button className="send" onClick={submit} disabled={pending || !value.trim()} type="button">
          发送
        </button>
      </div>
    </div>
  );
}

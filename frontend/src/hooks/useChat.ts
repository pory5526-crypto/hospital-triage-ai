import { useCallback, useRef, useState } from 'react';
import { streamChat } from '../lib/api';
import type { ChatMessage, HandoffInfo } from '../lib/types';

const uid = () => Math.random().toString(36).slice(2, 10);

interface SendOptions {
  imageText?: string;
  fileName?: string;
  file?: { name: string };
  /** 气泡里显示给用户的文字，缺省等于 message */
  displayText?: string;
}

interface UseChatParams {
  onHandoff: (info: HandoffInfo) => void;
  onToast: (text: string) => void;
}

export function useChat({ onHandoff, onToast }: UseChatParams) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const sessionRef = useRef<string | undefined>();
  const currentRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastRef = useRef<{ message: string; imageText?: string; fileName?: string } | null>(null);

  const ensureAssistant = useCallback(() => {
    if (currentRef.current) return currentRef.current;
    const id = uid();
    currentRef.current = id;
    setMessages((prev) => [...prev, { id, role: 'assistant', text: '', streaming: true }]);
    return id;
  }, []);

  const patch = useCallback((id: string, updater: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)));
  }, []);

  const seed = useCallback((text: string, chips?: string[]) => {
    setMessages([{ id: 'welcome', role: 'assistant', text, chips }]);
    currentRef.current = null;
  }, []);

  const send = useCallback(
    async (message: string, opts: SendOptions = {}) => {
      if (pending) return;
      const shown = (opts.displayText ?? message).trim();
      if (!shown && !opts.file) return;

      const userMsg: ChatMessage = {
        id: uid(),
        role: 'user',
        text: shown || (opts.file ? '' : ''),
        file: opts.file ? { name: opts.file.name, status: 'done' } : undefined,
      };
      setMessages((prev) => [...prev, userMsg]);
      currentRef.current = null;
      setPending(true);
      lastRef.current = {
        message,
        imageText: opts.imageText,
        fileName: opts.file?.name,
      };

      const controller = new AbortController();
      abortRef.current = controller;
      let handedOff = false;

      try {
        await streamChat({
          sessionId: sessionRef.current,
          message,
          imageText: opts.imageText,
          fileName: opts.file?.name,
          signal: controller.signal,
          onEvent: (event) => {
            switch (event.type) {
              case 'meta':
                sessionRef.current = event.sessionId;
                setSessionId(event.sessionId);
                break;
              case 'delta': {
                const id = ensureAssistant();
                patch(id, (m) => ({ ...m, text: m.text + event.text, streaming: true }));
                break;
              }
              case 'card': {
                const id = ensureAssistant();
                patch(id, (m) => ({ ...m, card: event.card }));
                break;
              }
              case 'segment_end': {
                if (currentRef.current) {
                  const id = currentRef.current;
                  patch(id, (m) => ({ ...m, streaming: false }));
                }
                currentRef.current = null;
                break;
              }
              case 'handoff':
                handedOff = true;
                onHandoff(event.handoff);
                break;
              case 'error':
                if (!event.silent) onToast(event.message);
                break;
              case 'done':
                break;
              default:
                break;
            }
          },
        });
      } catch (err) {
        const controllerAborted = controller.signal.aborted;
        if (!controllerAborted) {
          const message2 = err instanceof Error ? err.message : '网络异常';
          setMessages((prev) => [
            ...prev,
            {
              id: uid(),
              role: 'assistant',
              text: `连接失败：${message2}。请检查网络后重试，或点击下方「转人工客服」联系导诊台。`,
            },
          ]);
          onToast('回复失败，可重试');
        }
      } finally {
        if (currentRef.current) {
          const id = currentRef.current;
          patch(id, (m) => ({ ...m, streaming: false }));
          currentRef.current = null;
        }
        abortRef.current = null;
        setPending(false);
      }

      if (handedOff) {
        // 转人工时同步收起输入态
        setPending(false);
      }
    },
    [onHandoff, onToast, patch, pending, ensureAssistant],
  );

  const retry = useCallback(() => {
    const last = lastRef.current;
    if (!last || pending) return;
    setMessages((prev) => prev.filter((m) => m.role === 'user' || m.text.length > 0 || m.card));
    void send(last.message, {
      imageText: last.imageText,
      fileName: last.fileName,
      file: last.fileName ? { name: last.fileName } : undefined,
    });
  }, [pending, send]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { messages, pending, sessionId: sessionId, send, seed, retry, stop };
}

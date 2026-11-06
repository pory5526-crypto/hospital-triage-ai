import { useCallback, useEffect, useRef, useState } from 'react';
import { uploadAudio } from '../lib/api';

interface Options {
  sessionId?: string;
  onFinal: (text: string) => void;
  onError: (message: string) => void;
}

const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
  'audio/aac',
];

function pickMime(): string {
  if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) return '';
  return MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported(m)) ?? '';
}

function extOf(mime: string): string {
  if (mime.includes('webm')) return 'webm';
  if (mime.includes('mp4')) return 'mp4';
  if (mime.includes('ogg')) return 'ogg';
  if (mime.includes('aac')) return 'aac';
  return 'webm';
}

/** 浏览器只在安全上下文（HTTPS / localhost）开放麦克风 */
function isSecure(): boolean {
  if (typeof window === 'undefined') return false;
  if (window.isSecureContext) return true;
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1';
}

/**
 * 网页端语音输入：录音 → 上传后端 ASR 转文字。
 *
 * 不用 Web Speech API，原因是它在很多浏览器（尤其微信 WebView、非 Chrome）
 * 只触发 start 不触发任何回调，界面会永远卡在「正在聆听」。
 */
export function useSpeech({ sessionId, onFinal, onError }: Options) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const tickRef = useRef<number | null>(null);
  const maxTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const hasRecorder =
      typeof navigator !== 'undefined' &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof MediaRecorder !== 'undefined';
    setSupported(hasRecorder && isSecure());
    return () => {
      if (tickRef.current) window.clearInterval(tickRef.current);
      if (maxTimerRef.current) window.clearTimeout(maxTimerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const cleanup = useCallback(() => {
    if (tickRef.current) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (maxTimerRef.current) {
      window.clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recorderRef.current = null;
    setListening(false);
    setElapsed(0);
  }, []);

  const start = useCallback(async () => {
    if (transcribing) return;

    if (!isSecure()) {
      onError('手机浏览器在 http 下不开放麦克风，请用小程序版语音，或把网页部署成 https');
      return;
    }
    if (!supported) {
      onError('当前浏览器不支持录音，请改用文字描述');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mime = pickMime();
      const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        const durationMs = Date.now() - startedAtRef.current;
        const type = recorder.mimeType || mime || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type });
        cleanup();

        if (durationMs < 600 || blob.size < 1200) {
          onError('录音太短，请按住多说两句');
          return;
        }

        setTranscribing(true);
        try {
          const text = await uploadAudio(blob, `voice.${extOf(type)}`, sessionId);
          if (text) onFinal(text);
          else onError('没听清，请再说一次');
        } catch (err) {
          onError(err instanceof Error ? err.message : '语音识别失败，请改用文字');
        } finally {
          setTranscribing(false);
        }
      };

      recorder.start();
      recorderRef.current = recorder;
      startedAtRef.current = Date.now();
      setListening(true);
      setElapsed(0);

      tickRef.current = window.setInterval(() => {
        setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }, 500);

      // 最长 60 秒自动结束，避免用户忘了点
      maxTimerRef.current = window.setTimeout(() => {
        try {
          recorder.state !== 'inactive' && recorder.stop();
        } catch {
          cleanup();
        }
      }, 60_000);
    } catch (err) {
      cleanup();
      const name = err instanceof Error ? err.name : '';
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        onError('麦克风权限被拒绝，请在浏览器设置里允许后重试');
      } else if (name === 'NotFoundError') {
        onError('没有检测到麦克风设备');
      } else {
        onError('录音启动失败，请改用文字描述');
      }
    }
  }, [cleanup, onError, onFinal, sessionId, supported, transcribing]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      cleanup();
      return;
    }
    try {
      recorder.stop();
    } catch {
      cleanup();
    }
  }, [cleanup]);

  return { supported, listening, transcribing, elapsed, start, stop };
}

import type { ClientConfig, StreamEvent, UploadResult } from './types';

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function getConfig(): Promise<ClientConfig> {
  return request<ClientConfig>('/api/config');
}

export function createSession(channel = 'miniprogram'): Promise<{
  sessionId: string;
  welcome: ClientConfig['welcome'];
  hospital: string;
}> {
  return request('/api/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel }),
  });
}

export function postEvent(sessionId: string, event: string, payload: Record<string, unknown> = {}) {
  void fetch(`${BASE}/api/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, event, payload }),
  }).catch(() => undefined);
}

export async function uploadFile(file: File, sessionId: string): Promise<UploadResult> {
  const form = new FormData();
  form.append('file', file, file.name);
  const res = await fetch(`${BASE}/api/upload`, {
    method: 'POST',
    headers: { 'x-session-id': sessionId },
    body: form,
  });
  const body = (await res.json().catch(() => ({}))) as Partial<UploadResult> & { detail?: string };
  if (!res.ok) {
    throw new Error(body.detail || `上传失败（HTTP ${res.status}）`);
  }
  return {
    ok: Boolean(body.ok),
    fileName: body.fileName || file.name,
    text: body.text || '',
    chars: body.chars,
    error: body.error ?? null,
    hint: body.hint,
  };
}

/** 语音转文字：把录音 Blob 传给后端 ASR。 */
export async function uploadAudio(
  blob: Blob,
  filename = 'voice.webm',
  sessionId = '',
): Promise<string> {
  const form = new FormData();
  form.append('file', blob, filename);
  const res = await fetch(`${BASE}/api/asr`, {
    method: 'POST',
    headers: { 'x-session-id': sessionId },
    body: form,
  });
  const body = (await res.json().catch(() => ({}))) as { ok?: boolean; text?: string; error?: string };
  if (!res.ok) throw new Error(body.error || `语音识别失败（HTTP ${res.status}）`);
  if (!body.ok || !body.text) throw new Error(body.error || '没听清，请再说一次');
  return body.text;
}

interface StreamOptions {
  sessionId?: string;
  message: string;
  imageText?: string;
  fileName?: string;
  signal?: AbortSignal;
  onEvent: (event: StreamEvent) => void;
}

export async function streamChat(opts: StreamOptions): Promise<void> {
  const res = await fetch(`${BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId: opts.sessionId,
      message: opts.message,
      imageText: opts.imageText,
      fileName: opts.fileName,
    }),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`对话接口异常（HTTP ${res.status}）`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx = buffer.indexOf('\n\n');
    while (idx >= 0) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = raw.split('\n').find((l) => l.startsWith('data:'));
      if (line) {
        const payload = line.slice(5).trim();
        if (payload) {
          try {
            opts.onEvent(JSON.parse(payload) as StreamEvent);
          } catch {
            /* 忽略半包 */
          }
        }
      }
      idx = buffer.indexOf('\n\n');
    }
  }
}

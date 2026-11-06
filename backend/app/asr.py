"""语音识别：走千问平台的录音转写模型（DashScope 同步接口）。

小程序端用 RecorderManager 录音 → 上传到这里 → 返回文字 → 当成普通消息发出去。
"""

from __future__ import annotations

import base64

import httpx

from .config import settings

_MIME = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "mp4": "audio/mp4",
    "aac": "audio/aac",
    "amr": "audio/amr",
    "ogg": "audio/ogg",
    "webm": "audio/webm",
}

# 这些情况当成「没听清」而不是「系统故障」
_SOFT_HINTS = ("NO_WORDS", "EMPTY", "NO_SPEECH", "SILENCE", "INVALID_AUDIO", "TOO_SHORT")

_MSG_NO_SPEECH = "没听清，请再说一次，或者改用文字描述"
_MSG_UNAVAILABLE = "语音识别暂时不可用，请改用文字描述"


class AsrError(RuntimeError):
    pass


def endpoint() -> str:
    """从 base_url 推出 DashScope 端点（base_url 是 OpenAI 兼容路径）。"""
    if settings.asr_url:
        return settings.asr_url
    base = settings.llm_base_url.rstrip("/")
    host = base.split("/compatible-mode")[0]
    return host + "/api/v1/services/aigc/multimodal-generation/generation"


async def transcribe(data: bytes, fmt: str = "mp3") -> tuple[str, str | None]:
    """返回 (文本, 错误说明)。没听清时文本为空、错误说明给友好文案。"""
    if not settings.llm_enabled:
        return "", "语音识别需要先配置大模型 Key"

    if not data:
        return "", "没有录到声音，请再说一次"
    if len(data) > 10 * 1024 * 1024:
        return "", "录音太长，请控制在 1 分钟以内"

    mime = _MIME.get(fmt.lower(), "audio/mpeg")
    data_uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"

    payload = {
        "model": settings.asr_model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "input_audio", "input_audio": {"data": data_uri}}],
                }
            ]
        },
        "parameters": {"format": fmt.lower(), "sample_rate": "16000"},
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
        "X-DashScope-SSE": "disable",
    }

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(endpoint(), headers=headers, json=payload)
    except httpx.HTTPError:
        return "", _MSG_UNAVAILABLE

    try:
        body = resp.json()
    except ValueError:
        return "", _MSG_UNAVAILABLE

    if resp.status_code >= 400:
        # 只做内部日志，对外一律给中文提示，绝不把错误码抛给患者
        blob = f"{body.get('code', '')} {body.get('message', '')}".upper()
        if any(hint in blob for hint in _SOFT_HINTS):
            return "", _MSG_NO_SPEECH
        print(f"[asr] 识别失败 {resp.status_code}: {blob[:200]}")
        return "", _MSG_UNAVAILABLE

    output = body.get("output") or {}
    text = (output.get("text") or (output.get("sentence") or {}).get("text") or "").strip()
    if not text:
        return "", _MSG_NO_SPEECH
    return text, None

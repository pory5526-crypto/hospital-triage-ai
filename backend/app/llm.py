"""大模型客户端：任何 OpenAI 兼容接口（DeepSeek / Qwen / GLM / Ollama / vLLM）。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from .config import settings


class LLMError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


def _endpoint() -> str:
    return settings.llm_base_url.rstrip("/") + "/chat/completions"


async def stream_chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    """流式返回增量文本。"""
    if not settings.llm_enabled:
        raise LLMError("LLM 未配置")

    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": True,
        "temperature": settings.llm_temperature if temperature is None else temperature,
        "max_tokens": settings.llm_max_tokens if max_tokens is None else max_tokens,
    }
    if settings.llm_enable_thinking:
        payload["enable_thinking"] = settings.llm_enable_thinking.lower() == "true"
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    timeout = httpx.Timeout(settings.llm_timeout, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", _endpoint(), json=payload, headers=_headers()
            ) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread())[:400]
                    raise LLMError(f"LLM HTTP {resp.status_code}: {body!r}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk in ("", "[DONE]"):
                        continue
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield text
    except httpx.TimeoutException as exc:
        raise LLMError("模型响应超时") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"模型连接失败: {exc}") from exc


async def complete_chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 400,
) -> dict:
    """非流式调用，用于意图判断 / Function Call 规划。"""
    if not settings.llm_enabled:
        raise LLMError("LLM 未配置")

    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if settings.llm_enable_thinking:
        payload["enable_thinking"] = settings.llm_enable_thinking.lower() == "true"
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    timeout = httpx.Timeout(min(12.0, settings.llm_timeout), connect=8.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_endpoint(), json=payload, headers=_headers())
            if resp.status_code >= 400:
                raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
            return resp.json()
    except httpx.TimeoutException as exc:
        raise LLMError("模型响应超时") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"模型连接失败: {exc}") from exc


async def health() -> dict:
    """轻量连通性检查，不消耗对话额度。"""
    if not settings.llm_enabled:
        return {"configured": False, "reachable": False, "model": settings.llm_model}
    try:
        await complete_chat([{"role": "user", "content": "ping"}], max_tokens=4)
        return {"configured": True, "reachable": True, "model": settings.llm_model}
    except LLMError as exc:
        return {"configured": True, "reachable": False, "model": settings.llm_model, "error": str(exc)}

"""系统提示词装载：从 data/persona.md 读取，按医院配置渲染，改文件即生效（按 mtime 热更新）。"""

from __future__ import annotations

from pathlib import Path

from .config import DATA_DIR, DISCLAIMER, settings

_PERSONA_PATH = DATA_DIR / "persona.md"

_cache: dict[str, object] = {"mtime": -1.0, "text": ""}

_FALLBACK = (
    "你是医院智能导诊助手，只提供科室推荐、就诊流程与院内规则答疑。"
    "严禁给出诊断、病情轻重判断、用药建议、疗效或预后判断。"
    "院内信息只能引用提供的资料，没有就说查不到并给导诊台电话。"
)


def _render(raw: str) -> str:
    mapping = {
        "{hospital}": settings.hospital_name,
        "{triage_phone}": settings.triage_phone,
        "{emergency_phone}": settings.emergency_phone,
        "{service_hours}": settings.service_hours,
        "{disclaimer}": DISCLAIMER,
    }
    text = raw
    for key, value in mapping.items():
        text = text.replace(key, value)
    return text.strip()


def load_system_prompt() -> str:
    """读取并渲染 persona.md；文件改动后自动生效。"""
    try:
        mtime = _PERSONA_PATH.stat().st_mtime
    except OSError:
        return _FALLBACK

    if mtime != _cache["mtime"]:
        try:
            raw = _PERSONA_PATH.read_text(encoding="utf-8")
            _cache["text"] = _render(raw)
            _cache["mtime"] = mtime
        except OSError:
            return _FALLBACK

    return str(_cache["text"] or _FALLBACK)


def persona_path() -> Path:
    return _PERSONA_PATH


def invalidate() -> None:
    _cache["mtime"] = -1.0


def stats() -> dict:
    text = load_system_prompt()
    return {
        "path": str(_PERSONA_PATH),
        "exists": _PERSONA_PATH.exists(),
        "chars": len(text),
        "updatedAt": int(_cache["mtime"]) if isinstance(_cache["mtime"], float) else 0,
    }

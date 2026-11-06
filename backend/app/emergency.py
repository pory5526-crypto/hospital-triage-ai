"""急症分流：规则优先，命中即中断普通分诊。"""

from __future__ import annotations

import re
from functools import lru_cache

from .config import settings
from .store import get_data

_NEGATIONS = ("不", "没", "无", "未", "非", "别")


def _negated(text: str, idx: int) -> bool:
    """简单否定判断：关键词前 4 个字里出现否定词则视为否定（如「没有胸痛」）。"""
    window = text[max(0, idx - 4) : idx]
    return any(n in window for n in _NEGATIONS)


@lru_cache(maxsize=64)
def _compile(pattern: str) -> re.Pattern | None:
    try:
        return re.compile(pattern)
    except re.error:
        return None


def detect(text: str) -> dict | None:
    if not text:
        return None
    data = get_data()
    rules = data.emergency.get("rules", [])

    # 1) 关键词命中（带否定判断）
    for rule in rules:
        for kw in rule.get("keywords", []):
            start = 0
            while True:
                idx = text.find(kw, start)
                if idx < 0:
                    break
                if not _negated(text, idx):
                    return build_payload(rule, kw)
                start = idx + len(kw)

    # 2) 正则模式命中（覆盖「吐出一大口血」「嘴巴歪了」这类口语组合）
    for rule in rules:
        for pattern in rule.get("patterns", []) or []:
            regex = _compile(pattern)
            if regex is None:
                continue
            match = regex.search(text)
            if match and not _negated(text, match.start()):
                return build_payload(rule, match.group(0))

    return None


def build_payload(rule: dict, keyword: str) -> dict:
    data = get_data()
    em = data.emergency
    return {
        "type": "emergency",
        "label": rule.get("label", "急症"),
        "keyword": keyword,
        "title": f"检测到「{rule.get('label', keyword)}」，请立即前往急诊",
        "advice": rule.get("advice", ""),
        "location": em.get("location", "急诊楼 1F"),
        "phone": em.get("phone", settings.emergency_phone),
        "route": em.get("route", []),
        "disclaimer": "急症情况请勿等待线上回复，立即呼叫 120 或前往急诊。",
    }


def text_of(payload: dict) -> str:
    """急症气泡只负责把患者拉走，具体处置、位置、路线全部交给下面的急诊卡，避免重复。"""
    return (
        f"好的，您描述的「{payload['label']}」属于需要紧急处理的情况，我先帮您转急诊。\n"
        "请按下面的指引立刻前往，不要在这里等回复。"
    )

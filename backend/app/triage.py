"""智能分诊：症状关键词 → 科室加权打分 → 首选 / 备选科室 + 匹配度。"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache

from .config import settings
from .llm import LLMError, complete_chat
from .store import get_data

_AGE = re.compile(r"(\d{1,2})\s*岁")
_CHILD_WORDS = ("孩子", "小孩", "宝宝", "儿童", "婴儿", "幼儿", "儿子", "女儿", "小朋友", "闺女", "娃")
_NEGATIONS = ("不", "没", "无", "未", "非")

# 低于这个分数认为信息不足，先追问而不是硬推科室
MIN_SCORE = 0.45
MAX_ALTERNATIVES = 2


def _negated(text: str, idx: int) -> bool:
    window = text[max(0, idx - 4) : idx]
    return any(n in window for n in _NEGATIONS)


def _hits(text: str, keywords: list[str]) -> list[str]:
    found: list[str] = []
    for kw in keywords:
        if not kw:
            continue
        start = 0
        while True:
            idx = text.find(kw, start)
            if idx < 0:
                break
            if not _negated(text, idx):
                found.append(kw)
                break
            start = idx + len(kw)
    return found


@lru_cache(maxsize=128)
def _compile(pattern: str) -> re.Pattern | None:
    try:
        return re.compile(pattern)
    except re.error:
        return None


def _pattern_hits(text: str, patterns: list[str]) -> list[str]:
    """正则模式命中：用来覆盖「耳朵里嗡嗡响」「稍微走快点就喘」这类口语组合。"""
    found: list[str] = []
    for pattern in patterns or []:
        regex = _compile(pattern)
        if regex is None:
            continue
        match = regex.search(text)
        if match and not _negated(text, match.start()):
            found.append(match.group(0))
    return found


def _is_child(text: str) -> bool:
    if any(w in text for w in _CHILD_WORDS):
        return True
    for match in _AGE.finditer(text):
        try:
            if int(match.group(1)) < 15:
                return True
        except ValueError:
            continue
    return False


def analyze(text: str) -> dict | None:
    """返回分诊卡片数据；信息不足返回 None（由调用方追问）。"""
    if not text or len(text.strip()) < 2:
        return None

    data = get_data()
    scores: dict[str, float] = defaultdict(float)
    matched_terms: list[str] = []
    matched_rules: list[dict] = []
    rule_hits: list[int] = []

    # ---------- 1. 规则打分 ----------
    for rule in data.triage_rules:
        hits = _hits(text, rule.get("keywords", []))
        pat_hits = _pattern_hits(text, rule.get("patterns", []))
        if not hits and not pat_hits:
            continue
        matched_rules.append(rule)
        rule_hits.append(len(hits) + len(pat_hits))
        matched_terms.extend((hits + pat_hits)[:2])
        # 命中多个关键词时轻微增益，但不线性放大
        gain = 1.0 + min(0.35, 0.12 * (len(hits) + len(pat_hits) - 1))
        for dept, weight in (rule.get("scores") or {}).items():
            scores[dept] += float(weight) * gain

    # ---------- 2. 科室自有症状词兜底加分 ----------
    for dept in data.departments:
        pool = list(dept.get("symptoms", [])) + list(dept.get("keywords", []))
        hits = _hits(text, pool)
        if hits:
            scores[dept["name"]] += min(0.5, 0.14 * len(hits))
            if not matched_rules:
                matched_terms.extend(hits[:2])

    # ---------- 3. 人群规则 ----------
    population: str | None = None
    if _is_child(text):
        population = "儿童"
        scores["儿科"] += 1.3
        for name in list(scores.keys()):
            if name not in ("儿科", "儿童保健科"):
                scores[name] *= 0.45
        if "儿科" not in scores:
            scores["儿科"] = 1.3

    for pop in data.populations:
        if pop.get("id") == "p-child":
            continue
        if not any(kw in text for kw in pop.get("keywords", [])):
            continue
        population = population or pop.get("label")
        for dept, boost in (pop.get("boost") or {}).items():
            scores[dept] = scores.get(dept, 0.0) + float(boost)
        dampen = float(pop.get("dampen", 1.0))
        if dampen != 1.0:
            for name in list(scores.keys()):
                if name not in (pop.get("boost") or {}):
                    scores[name] *= dampen

    scores = {k: v for k, v in scores.items() if v > 0 and k in data.dept_by_name}
    if not scores:
        return None

    top_dept, top_score = max(scores.items(), key=lambda kv: kv[1])
    if top_score < MIN_SCORE:
        return None

    # ---------- 4. 匹配度归一化 ----------
    def to_pct(value: float) -> int:
        ratio = value / top_score if top_score else 0
        return max(45, min(96, round(45 + 51 * ratio)))

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    primary = {
        "dept": top_dept,
        "match": 96,
        "label": "建议优先就诊",
        "location": data.dept_by_name[top_dept].get("location", ""),
    }

    alternatives = []
    for name, value in ordered[1:]:
        if len(alternatives) >= MAX_ALTERNATIVES:
            break
        if value / top_score < 0.33:
            continue
        alternatives.append(
            {
                "dept": name,
                "match": to_pct(value),
                "label": "备选排查",
                "location": data.dept_by_name[name].get("location", ""),
            }
        )

    # ---------- 5. 分析说明（模板化，不交给模型自由发挥）----------
    terms = _dedup(matched_terms)[:4]
    term_text = "、".join(terms) if terms else "您描述的症状"
    intro = data.dept_by_name[top_dept].get("intro", "")
    note_parts = [f"根据您描述的「{term_text}」，建议优先就诊{top_dept}。"]
    if intro:
        note_parts.append(intro)
    if population:
        note_parts.append(f"您提到是{population}，已优先按对应分诊规则匹配。")
    if alternatives:
        note_parts.append(f"若{top_dept}排查无明确异常，可再前往{alternatives[0]['dept']}进一步检查。")

    return {
        "type": "triage",
        "primary": primary,
        "alternatives": alternatives,
        "note": "".join(note_parts),
        "matched": terms,
        "population": population,
        "rule_count": len(matched_rules),
        "confidence": round(min(0.99, top_score / (top_score + 0.8)), 3),
    }


def _dedup(items: list[str]) -> list[str]:
    seen: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.append(it)
    return seen


def clarify_text() -> str:
    data = get_data()
    clarify = data.clarify or {}
    intro = clarify.get("intro", "为了给您更准确的科室建议，我需要再确认几个信息：")
    questions = clarify.get("questions", [])[:2]
    if not questions:
        return intro
    return intro + "\n" + "\n".join(f"· {q}" for q in questions)


def primary_dept_of(card: dict) -> str:
    return (card.get("primary") or {}).get("dept", "")


# ---------------------------------------------------------------- 模型兜底分类
_CLASSIFY_SYSTEM = """你是医院分诊助手。根据患者的症状描述，从给定的科室列表里选出最合适的科室。

要求：
1. 只能从列表里的科室名中选，一个字都不能改，不能编造科室。
2. 首选 1 个，备选最多 2 个，备选不能和首选相同。
3. match 是 45-96 的整数，表示症状与该科室的匹配程度，首选最高。
4. **如果这句话不是身体症状描述**（例如在问流程、问政策、问位置、问价格），一律返回空 primary。
5. 症状太笼统、完全无法判断时，也返回空 primary。
6. 只返回 JSON，不要任何解释文字，不要 markdown 代码块。

返回格式：
{"primary":"科室名","match":92,"alternatives":[{"dept":"科室名","match":74}]}
或无法判断时：
{"primary":"","match":0,"alternatives":[]}"""


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


async def classify_with_llm(text: str) -> dict | None:
    """规则认不出来时，让模型从封闭科室清单里选，避免直接反问答非所问。"""
    if not settings.llm_enabled:
        return None

    data = get_data()
    catalog = "\n".join(
        f"- {d['name']}（{d.get('intro', '')}）" for d in data.departments
    )
    messages = [
        {"role": "system", "content": _CLASSIFY_SYSTEM + "\n\n可选科室：\n" + catalog},
        {"role": "user", "content": text},
    ]

    try:
        result = await complete_chat(messages, temperature=0, max_tokens=200)
    except LLMError:
        return None

    choices = result.get("choices") or []
    if not choices:
        return None
    parsed = _parse_json((choices[0].get("message") or {}).get("content", ""))
    if not parsed:
        return None

    primary_name = (parsed.get("primary") or "").strip()
    if not primary_name or primary_name not in data.dept_by_name:
        return None

    def clamp(value, lo=45, hi=96) -> int:
        try:
            return max(lo, min(hi, int(value)))
        except (TypeError, ValueError):
            return lo

    top = clamp(parsed.get("match", 90))
    alternatives = []
    for alt in parsed.get("alternatives") or []:
        name = (alt.get("dept") or "").strip()
        if not name or name == primary_name or name not in data.dept_by_name:
            continue
        if len(alternatives) >= MAX_ALTERNATIVES:
            break
        alternatives.append(
            {
                "dept": name,
                "match": min(clamp(alt.get("match", 70)), top - 1),
                "label": "备选排查",
                "location": data.dept_by_name[name].get("location", ""),
            }
        )

    dept = data.dept_by_name[primary_name]
    note = f"根据您描述的情况，建议优先就诊{primary_name}。{dept.get('intro', '')}"
    if alternatives:
        note += f"若{primary_name}排查无明确异常，可再前往{alternatives[0]['dept']}进一步检查。"

    return {
        "type": "triage",
        "primary": {
            "dept": primary_name,
            "match": top,
            "label": "建议优先就诊",
            "location": dept.get("location", ""),
        },
        "alternatives": alternatives,
        "note": note,
        "matched": [],
        "population": None,
        "rule_count": 0,
        "confidence": round(top / 100, 3),
        "by": "llm",
    }


async def analyze_async(text: str) -> dict | None:
    """先走规则（可复现、可审计），规则认不出再让模型兜底。"""
    card = analyze(text)
    if card:
        card.setdefault("by", "rules")
        return card
    return await classify_with_llm(text)

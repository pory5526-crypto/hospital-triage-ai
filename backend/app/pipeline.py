"""对话编排：意图路由 → 急症分流 → 智能分诊 → 知识库问答 → 流式作答。

对外只暴露一个异步生成器 `respond`，产出事件流：
    {"type": "meta", ...}
    {"type": "delta", "text": "..."}
    {"type": "card", "card": {...}}
    {"type": "segment_end"}            # 结束当前气泡，后续 delta 另起一条
    {"type": "handoff", "handoff": {...}}
    {"type": "done", ...}
    {"type": "error", "message": "..."}
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from . import emergency, tools, triage
from .config import DISCLAIMER, settings
from .llm import LLMError, stream_chat
from .prompt import load_system_prompt
from .rag import kb
from .session import Session
from .store import get_data
from .telemetry import log_event, record_latency

_HANDOFF_WORDS = ("转人工", "人工客服", "找个人", "真人", "投诉", "态度", "举报", "客服电话", "打不通")
_OUT_OF_SCOPE = (
    "吃什么药", "用什么药", "吃啥药", "药量", "开点药", "开药", "推荐药",
    "是不是得", "是不是癌", "确诊", "能治好吗", "能治愈", "严重吗", "会不会死",
    "偏方", "化疗方案", "手术要不要做", "要不要住院", "几天能好",
)
_FOLLOWUP_HINTS = (
    "就诊前请带上身份证和医保卡，如果已经有之前的检查报告或正在吃的药，可以直接发给我，我帮您一起看。",
    "挂号可以走医院自助机或门诊楼 1F 的人工窗口，线上挂号功能正在开发中。",
    "如果等待过程中症状加重，请直接到急诊楼 1F，不要继续排队。",
)

# 问「你们医院有没有 XX」这类院内事实，不该反问他症状
_FACT_SUBJECTS = ("你们", "贵院", "本院", "咱医院", "咱们医院")
_FACT_ASKS = ("有没有", "有吗", "能不能", "可不可以", "多少个", "几张", "多少张", "叫什么", "是谁", "多少位")

_GREETINGS = ("你好", "您好", "在吗", "在么", "哈喽", "hello", "hi", "嗨", "早上好", "中午好", "下午好", "晚上好", "有人吗")
_THANKS = ("谢谢", "感谢", "多谢", "辛苦了", "麻烦你了")
_BYE = ("再见", "拜拜", "没事了", "不用了", "好的谢谢")

_GREETING_REPLY = (
    "您好，我是小医助。您哪里不舒服？说一下主要症状和大概持续多久，"
    "我帮您判断该挂哪个科室。"
)
_THANKS_REPLY = "不客气。还有哪里不舒服随时问我；需要挂号或就诊流程指引也可以直接说。"


def _smalltalk_reply(text: str) -> str | None:
    """寒暄、道谢这类话不该被当成症状去追问。"""
    t = (text or "").strip()
    if not t or len(t) > 12:
        return None
    if any(w in t for w in _THANKS):
        return _THANKS_REPLY
    if any(w in t for w in _GREETINGS):
        return _GREETING_REPLY
    return None


def _looks_like_hospital_fact(text: str) -> bool:
    if any(s in text for s in _FACT_SUBJECTS):
        return True
    return any(a in text for a in _FACT_ASKS)


def _dedup(items: list[str]) -> list[str]:
    out: list[str] = []
    for it in items:
        if it and it not in out:
            out.append(it)
    return out


# ------------------------------------------------------------------ 上下文拼装
def _kb_context(hits) -> str:
    if not hits:
        return ""
    lines = [f"- {h.item['title']}：{h.item['content']}" for h in hits]
    return "【院内资料】\n" + "\n".join(lines)


def _triage_context(card: dict) -> str:
    alts = "、".join(f"{a['dept']}({a['match']}%)" for a in card.get("alternatives", []))
    return (
        "【分诊结果（系统规则已确定，直接采用）】\n"
        f"首选科室：{card['primary']['dept']}（匹配度 {card['primary']['match']}%）\n"
        f"备选科室：{alts or '无'}\n"
        f"依据：{card['note']}"
    )


def _build_messages(session: Session, user_text: str, context_blocks: list[str]) -> list[dict]:
    ctx = "\n\n".join(b for b in context_blocks if b)
    system = load_system_prompt()
    if ctx:
        system += "\n\n以下是本轮可用的院内资料，回答必须基于它：\n" + ctx
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(session.history_for_llm())
    messages.append({"role": "user", "content": user_text})
    return messages


def _handoff_payload(reason: str) -> dict:
    data = get_data()
    hospital = data.hospital
    return {
        "reason": reason,
        "phone": settings.triage_phone or hospital.get("triage_phone", ""),
        "hours": settings.service_hours,
        "afterHoursTip": settings.after_hours_tip,
        "title": "联系人工导诊",
    }


# ------------------------------------------------------------------ 主流程
async def respond(
    session: Session,
    text: str,
    *,
    image_text: str = "",
    file_name: str = "",
) -> AsyncIterator[dict]:
    started = time.time()
    text = (text or "").strip()
    combined = text
    if image_text:
        combined = (text + "\n" + image_text).strip() if text else image_text

    if not combined:
        yield {"type": "error", "message": "请输入内容后再发送"}
        return

    # ---------- 1. 急症分流（最高优先级，且锁定后续对话）----------
    payload = emergency.detect(combined) if not session.emergency_locked else None

    if payload:
        session.emergency_locked = True
        session.add("user", combined, kind="text")
        body = emergency.text_of(payload)
        session.add("assistant", body, kind="emergency")
        log_event(
            "emergency_triggered",
            session.id,
            {"keyword": payload.get("keyword"), "label": payload.get("label")},
        )
        yield {"type": "delta", "text": body}
        yield {"type": "card", "card": payload}
        yield {"type": "segment_end"}
        yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}
        return

    log_event("message_sent", session.id, {"len": len(combined), "hasFile": bool(image_text)})

    # ---------- 2. 会话中已有急症锁定：持续引导急诊 ----------
    if session.emergency_locked:
        payload = emergency.build_payload(
            {"label": "急症", "advice": "您之前描述的情况属于急症范围，请优先到急诊就诊，不要继续等待线上回复。"},
            "",
        )
        body = "您的问诊还处在急诊优先状态，请您先到急诊楼 1F 处理，这边的问题可以稍后再问。"
        session.add("user", combined)
        session.add("assistant", body, kind="emergency")
        yield {"type": "delta", "text": body}
        yield {"type": "card", "card": payload}
        yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}
        return

    # ---------- 3. 转人工意图 ----------
    if any(w in combined for w in _HANDOFF_WORDS):
        body = (
            f"好的，人工导诊台电话是 {settings.triage_phone}，服务时间 {settings.service_hours}。"
            f"{settings.after_hours_tip}"
        )
        session.add("user", combined)
        session.add("assistant", body, kind="text")
        session.handoff_shown = True
        log_event("handoff", session.id, {"reason": "user_request"})
        yield {"type": "delta", "text": body}
        yield {"type": "handoff", "handoff": _handoff_payload("user_request")}
        yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}
        return

    # ---------- 4. 超出导诊边界 ----------
    if any(w in combined for w in _OUT_OF_SCOPE):
        body = (
            "这个问题涉及诊断和用药，我不能给建议，也不该替医生做判断。"
            "如果您愿意，告诉我具体不舒服的地方，我帮您判断该挂哪个科；"
            f"也可以直接联系导诊台 {settings.triage_phone}。"
        )
        session.add("user", combined)
        session.add("assistant", body, kind="boundary")
        log_event("handoff", session.id, {"reason": "out_of_scope"})
        yield {"type": "delta", "text": body}
        yield {"type": "handoff", "handoff": _handoff_payload("out_of_scope")}
        yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}
        return

    # ---------- 5. 寒暄 / 道谢（不能当成症状去追问）----------
    smalltalk = _smalltalk_reply(combined)
    if smalltalk:
        session.add("user", combined)
        session.add("assistant", smalltalk, kind="text")
        session.fail_streak = 0
        yield {"type": "delta", "text": smalltalk}
        yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}
        return

    # ---------- 6. 路由：结构化查询 / 分诊 / 知识库 / 追问 ----------
    structured = tools.needs_structured_lookup(combined)
    kb_hits = kb.retrieve(combined, top_k=settings.rag_top_k, min_confidence=settings.rag_min_score)

    triage_input = combined
    if session.awaiting_clarify:
        triage_input = f"{session.recent_user_text(2)} {combined}".strip()
    # 先只跑规则：规则命中就直接出卡（可复现、可审计）
    triage_card = None if structured else triage.analyze(triage_input)

    if triage_card:
        async for event in _answer_triage(session, combined, triage_card, started):
            yield event
        return

    if structured or kb_hits:
        async for event in _answer_knowledge(session, combined, kb_hits, structured, started):
            yield event
        return

    # 规则和知识库都没接住，才让模型从封闭科室清单里兜底分类
    if not structured:
        triage_card = await triage.classify_with_llm(triage_input)
        if triage_card:
            async for event in _answer_triage(session, combined, triage_card, started):
                yield event
            return

    # 未识别：先看是不是在问院内事实（这种情况不该反问症状），否则追问一次
    session.fail_streak += 1
    session.add("user", combined)

    if _looks_like_hospital_fact(combined):
        body = (
            "这个我这边查不到，建议您咨询导诊台 "
            f"{settings.triage_phone}。如果是身体不舒服，告诉我具体症状，我帮您判断挂哪个科。"
        )
        session.add("assistant", body, kind="fallback")
        yield {"type": "delta", "text": body}
        yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}
        return

    session.awaiting_clarify = True

    if session.fail_streak >= 2:
        body = (
            "抱歉，我没能准确理解您的问题。建议您直接联系导诊台获取帮助："
            f"{settings.triage_phone}。"
        )
        session.add("assistant", body, kind="fallback")
        log_event("handoff", session.id, {"reason": "fail_streak"})
        yield {"type": "delta", "text": body}
        yield {"type": "handoff", "handoff": _handoff_payload("fail_streak")}
    else:
        body = triage.clarify_text()
        session.add("assistant", body, kind="clarify")
        yield {"type": "delta", "text": body}

    yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}


async def _answer_triage(
    session: Session, combined: str, card: dict, started: float
) -> AsyncIterator[dict]:
    session.add("user", combined)
    session.last_triage = card
    session.awaiting_clarify = False
    session.fail_streak = 0

    lead = f"好的，我根据您的描述做了初步分诊，结果如下："
    contexts = [_triage_context(card)]
    problem = card["primary"]["dept"]
    hits = kb.retrieve(problem + " 就诊 注意事项", top_k=1, min_confidence=0.25)
    if hits:
        contexts.append(_kb_context(hits))

    text_out = lead
    if settings.llm_enabled:
        messages = _build_messages(
            session,
            f"{combined}\n\n（请只用一句话引导患者看下面的分诊结果，不要重复科室匹配度数字，不要给诊断结论。）",
            contexts,
        )
        try:
            chunks: list[str] = []
            async for chunk in stream_chat(messages, max_tokens=120):
                chunks.append(chunk)
                yield {"type": "delta", "text": chunk}
            text_out = "".join(chunks).strip() or lead
        except LLMError as exc:
            log_event("error", session.id, {"where": "triage", "error": str(exc)})
            text_out = lead
            yield {"type": "error", "message": "模型暂时不可用，已切换到基础分诊模式", "silent": True}

    if text_out == lead:
        yield {"type": "delta", "text": lead}

    yield {"type": "card", "card": card}
    yield {"type": "segment_end"}

    hint = _FOLLOWUP_HINTS[0]
    dept = get_data().dept(problem)
    if dept:
        hint = (
            f"{problem}在{dept.get('location', '')}，就诊前请带上身份证和医保卡，"
            "如果已经有之前的检查报告或正在吃的药，可以发给我一起看。"
        )
    session.add("assistant", text_out + "\n[卡片]" + card["note"] + "\n" + hint, kind="triage")
    yield {"type": "delta", "text": hint}
    log_event(
        "triage_shown",
        session.id,
        {
            "dept": problem,
            "confidence": card.get("confidence"),
            "alternatives": [a["dept"] for a in card.get("alternatives", [])],
            "population": card.get("population"),
        },
    )
    elapsed = time.time() - started
    record_latency(elapsed)
    yield {"type": "done", "latencyMs": int(elapsed * 1000)}


async def _answer_knowledge(
    session: Session, combined: str, kb_hits, structured: bool, started: float
) -> AsyncIterator[dict]:
    session.add("user", combined)
    session.awaiting_clarify = False
    session.fail_streak = 0

    tool_ctx = ""
    if structured:
        if settings.llm_enabled and settings.enable_tool_calling:
            try:
                tool_ctx, calls = await tools.plan_tool_calls(combined)
                if calls:
                    log_event("tool_call", session.id, {"calls": [c["name"] for c in calls]})
            except Exception as exc:  # noqa: BLE001
                log_event("error", session.id, {"where": "tool", "error": str(exc)})
        if not tool_ctx:
            tool_ctx = tools.resolve_context(combined)

    contexts = [c for c in (_kb_context(kb_hits), tool_ctx) if c]

    if not contexts:
        body = (
            "这个我这边查不到，建议您咨询导诊台 "
            f"{settings.triage_phone}，或者告诉我具体的不舒服，我帮您判断挂哪个科。"
        )
        session.add("assistant", body, kind="fallback")
        yield {"type": "delta", "text": body}
        yield {"type": "done", "latencyMs": int((time.time() - started) * 1000)}
        return

    text_out = ""
    if settings.llm_enabled:
        messages = _build_messages(session, combined, contexts)
        try:
            chunks: list[str] = []
            async for chunk in stream_chat(messages):
                chunks.append(chunk)
                yield {"type": "delta", "text": chunk}
            text_out = "".join(chunks).strip()
        except LLMError as exc:
            log_event("error", session.id, {"where": "kb", "error": str(exc)})
            yield {"type": "error", "message": "模型暂时不可用，已切换到资料直出模式", "silent": True}

    if not text_out:
        prefer_tool = any(w in combined for w in ("出诊", "专家", "医生", "排班", "余号", "挂号费"))
        text_out = _template_answer(kb_hits, tool_ctx, prefer_tool=prefer_tool)
        yield {"type": "delta", "text": text_out}

    session.add("assistant", text_out, kind="text")
    elapsed = time.time() - started
    record_latency(elapsed)
    yield {"type": "done", "latencyMs": int(elapsed * 1000)}


def _template_answer(kb_hits, tool_ctx: str, prefer_tool: bool = False) -> str:
    """未配置大模型时的直出模式：结构化查询优先用工具结果，其余用知识库原文。"""
    if prefer_tool and tool_ctx:
        return tool_ctx
    if kb_hits:
        top = kb_hits[0].item
        extra = kb_hits[1].item if len(kb_hits) > 1 else None
        body = f"{top['content']}"
        if extra and extra["category"] == top["category"]:
            body += f"\n另外：{extra['content']}"
        return body
    if tool_ctx:
        lines = [ln for ln in tool_ctx.splitlines() if ln.strip()]
        return "\n".join(lines[:8])
    return ""


def welcome() -> dict:
    data = get_data()
    hospital = data.hospital
    return {
        "text": (
            f"您好，我是智能导诊助手小医助。请用一两句话描述哪里不舒服、持续多久了，"
            "我帮您判断该挂哪个科室。"
        ),
        "hospital": hospital.get("name", settings.hospital_name),
        "subtitle": "智能分诊客服，7×24 小时在线",
        "chips": ["头晕心慌", "头痛发热", "腹痛腹泻", "咳嗽咽痛"],
        "disclaimer": DISCLAIMER,
    }

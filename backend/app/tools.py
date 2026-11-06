"""Function Call 工具层：查询科室位置、医生出诊、院内知识。

两种触发方式：
1. 大模型函数调用（需要配置 LLM，走 `plan_tool_calls`）；
2. 确定性路由（未配置 LLM 或模型没选工具时兜底，走 `resolve_context`）。
"""

from __future__ import annotations

import json
import re

from .llm import LLMError, complete_chat
from .rag import kb
from .store import get_data

WEEKDAYS = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}


# ---------------------------------------------------------------- 工具实现
def query_department(department: str) -> str:
    data = get_data()
    dept = data.dept(department)
    if not dept:
        # 模糊匹配：患者常说「心内科」「耳鼻喉」
        for name, info in data.dept_by_name.items():
            if department in name or name in department:
                dept = info
                break
    if not dept:
        return f"知识库里没有找到「{department}」这个科室，建议咨询导诊台 {data.hospital.get('triage_phone', '')}。"
    lines = [
        f"科室：{dept['name']}",
        f"位置：{dept.get('location', '')}",
        f"简介：{dept.get('intro', '')}",
    ]
    doctors = data.doctors_of(dept["name"])
    if doctors:
        lines.append("出诊医生：" + "、".join(f"{d['name']}（{d['title']}，¥{d['fee']}）" for d in doctors[:3]))
    return "\n".join(lines)


def query_doctor_schedule(department: str = "", weekday: int | None = None) -> str:
    data = get_data()
    pool = data.doctors
    if department:
        pool = [d for d in pool if department in d.get("dept", "") or d.get("dept", "") in department]
    if weekday:
        filtered = []
        for doc in pool:
            slots = [s for s in doc.get("schedule", []) if s.get("weekday") == weekday]
            if slots:
                filtered.append({**doc, "schedule": slots})
        pool = filtered
    if not pool:
        return "没有查到对应的出诊安排，建议以医院当日排班或挂号窗口为准。"
    lines: list[str] = []
    for doc in pool[:6]:
        slots = "；".join(
            f"{WEEKDAYS.get(s['weekday'], '')}{s['period']}（{s.get('room', '')}）"
            for s in doc.get("schedule", [])
        )
        lines.append(f"{doc['name']} {doc['title']}｜{doc['dept']}｜{slots}｜挂号费 ¥{doc['fee']}")
    return "\n".join(lines)


def query_locations() -> str:
    data = get_data()
    floors = data.hospital.get("floors", [])
    if not floors:
        return "暂无楼层信息。"
    return "\n".join(f"{f['name']}：{f['content']}" for f in floors)


def search_knowledge(query: str) -> str:
    hits = kb.retrieve(query, top_k=3, min_confidence=0.12)
    if not hits:
        return "知识库中没有检索到相关内容。"
    return "\n".join(f"- {h.item['title']}：{h.item['content']}" for h in hits)


def hospital_profile() -> str:
    data = get_data()
    h = data.hospital
    return (
        f"医院：{h.get('name', '')}\n地址：{h.get('address', '')}\n"
        f"门诊时间：{h.get('outpatient_hours', '')}\n导诊台电话：{h.get('triage_phone', '')}\n"
        f"急诊电话：{h.get('emergency_phone', '')}"
    )


# ---------------------------------------------------------------- OpenAI tools 定义
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "query_department",
            "description": "查询某个科室的位置、简介、出诊医生。患者问『XX科在哪』『XX科看什么』时调用。",
            "parameters": {
                "type": "object",
                "properties": {"department": {"type": "string", "description": "科室名称，如 心血管内科"}},
                "required": ["department"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_doctor_schedule",
            "description": "查询医生出诊表与挂号费。患者问『哪天有专家门诊』『某医生什么时候出诊』时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {"type": "string", "description": "科室名称，可为空"},
                    "weekday": {"type": "integer", "description": "星期几，1=周一 … 7=周日，可为空"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_locations",
            "description": "查询各楼层科室分布。患者问『放射科在几楼』『哪里抽血』类问题时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "检索院内知识库（医保、检查须知、挂号规则、取药、住院等）。",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "检索问题原文"}},
                "required": ["query"],
            },
        },
    },
]

_TOOL_IMPL = {
    "query_department": query_department,
    "query_doctor_schedule": query_doctor_schedule,
    "query_locations": query_locations,
    "search_knowledge": search_knowledge,
}

_STRUCTURED_HINTS = (
    "几楼", "哪层", "在哪", "位置", "怎么走", "楼层", "出诊", "专家门诊", "门诊时间",
    "几点", "挂号费", "多少钱", "排班", "余号", "停车", "窗口",
)

_WEEKDAY_WORDS = {
    "周一": 1, "星期一": 1, "周二": 2, "星期二": 2, "周三": 3, "星期三": 3,
    "周四": 4, "星期四": 4, "周五": 5, "星期五": 5, "周六": 6, "星期六": 6,
    "周日": 7, "周天": 7, "星期日": 7, "星期天": 7,
}


def needs_structured_lookup(text: str) -> bool:
    return any(h in text for h in _STRUCTURED_HINTS)


def _guess_department(text: str) -> str:
    data = get_data()
    best = ""
    for name in data.dept_by_name:
        short = name.replace("科", "")
        if name in text or (len(short) >= 3 and short in text):
            if len(name) > len(best):
                best = name
    return best


def resolve_context(question: str) -> str:
    """确定性工具路由：不依赖模型，保证演示时稳定返回。"""
    dept = _guess_department(question)
    weekday = next((v for k, v in _WEEKDAY_WORDS.items() if k in question), None)
    parts: list[str] = []

    if dept:
        parts.append(query_department(dept))
    if weekday or "出诊" in question or "专家" in question:
        parts.append(query_doctor_schedule(dept, weekday))
    if any(w in question for w in ("几楼", "哪层", "在哪", "楼层", "怎么走", "位置")):
        parts.append(query_locations())
    if any(w in question for w in ("医保", "报销", "停车", "抽血", "CT", "核磁", "取药", "发票", "住院")):
        parts.append(search_knowledge(question))

    return "\n\n".join(p for p in parts if p)


async def plan_tool_calls(question: str, timeout: float = 6.0) -> tuple[str, list[dict]]:
    """让模型自己决定调哪个工具。失败时返回空，由调用方降级到确定性路由。"""
    messages = [
        {
            "role": "system",
            "content": "你是医院导诊系统的工具调度器。判断回答用户问题是否需要查询院内结构化数据，需要就调用工具，不要回答用户。",
        },
        {"role": "user", "content": question},
    ]
    try:
        result = await complete_chat(messages, tools=TOOL_SPECS, max_tokens=200)
    except LLMError:
        return "", []

    calls: list[dict] = []
    choices = result.get("choices") or []
    if not choices:
        return "", []
    tool_calls = (choices[0].get("message") or {}).get("tool_calls") or []
    contexts: list[str] = []
    for call in tool_calls:
        fn = call.get("function") or {}
        name = fn.get("name", "")
        impl = _TOOL_IMPL.get(name)
        if not impl:
            continue
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        try:
            output = impl(**args)
        except TypeError:
            output = impl()
        contexts.append(f"[{name}] {output}")
        calls.append({"name": name, "args": args, "output": output})

    return "\n\n".join(contexts), calls

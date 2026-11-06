"""接口冒烟测试：覆盖 PRD V1 的主要分支。

用法（backend 目录下）：
    .venv\\Scripts\\python.exe scripts\\smoke_test.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CASES = [
    ("分诊-标准", "最近三天早上起来头晕，走快了会心慌，晚上也睡不好"),
    ("分诊-鼻炎", "鼻子一直塞，还老流鼻涕打喷嚏，之前说是鼻炎"),
    ("分诊-儿童", "孩子5岁，昨天开始发烧38度5，还一直咳嗽"),
    ("分诊-腹痛", "昨天中午开始肚子疼，拉了三次肚子，有点反酸"),
    ("急症-胸痛", "胸口疼得厉害，还一直冒汗"),
    ("急症-呼吸困难", "我爸突然喘不上气，嘴唇有点发紫"),
    ("知识库-医保", "异地医保怎么在这边直接结算"),
    ("知识库-位置", "放射科在几楼，Ct在哪里做"),
    ("知识库-抽血", "抽血需要空腹吗，早上能喝水吗"),
    ("工具-出诊", "心血管内科这周四出诊的医生有哪些"),
    ("转人工", "我要找人工客服"),
    ("超边界-用药", "我这个头晕吃什么药好"),
    ("边界-否定急症", "我没有胸痛，就是有点头晕"),
]


def run_case(client: httpx.Client, text: str) -> dict:
    """跑一轮对话，返回聚合结果。"""
    out = {"text": text, "deltas": [], "card": None, "handoff": None, "error": None}
    with client.stream(
        "POST", f"{BASE}/api/chat/stream", json={"message": text}, timeout=40
    ) as resp:
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "delta":
                out["deltas"].append(event["text"])
            elif kind == "card":
                out["card"] = event["card"]
            elif kind == "handoff":
                out["handoff"] = event["handoff"]
            elif kind == "error":
                out["error"] = event["message"]
    out["reply"] = "".join(out["deltas"]).replace("\n", " ")
    return out


def main() -> int:
    failures = 0
    with httpx.Client() as client:
        health = client.get(f"{BASE}/api/health", timeout=10).json()
        print(f"[env] 科室={health['departments']} 知识库={health['knowledge']} "
              f"医生={health['doctors']} LLM={health['llm']}\n")

        for name, text in CASES:
            res = run_case(client, text)
            card = res["card"] or {}
            if card.get("type") == "triage":
                verdict = f"分诊→{card['primary']['dept']} {card['primary']['match']}% / 备选 " + (
                    "、".join(f"{a['dept']}{a['match']}%" for a in card["alternatives"]) or "无"
                )
            elif card.get("type") == "emergency":
                verdict = f"急症→{card['label']}"
            elif res["handoff"]:
                verdict = f"转人工→{res['handoff']['reason']}"
            else:
                verdict = "普通回答"
            print(f"[{name}] {text}")
            print(f"    → {verdict}")
            print(f"    ↳ {res['reply'][:150]}")
            if res["error"]:
                print(f"    ! error: {res['error']}")
            if not res["reply"] and not card:
                failures += 1
                print("    ✗ 空回复")
            print()

    print(f"完成，空回复 {failures} 例")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

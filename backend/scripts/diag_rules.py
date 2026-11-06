"""分诊 / 急症 规则的快速诊断（进程内，不走 HTTP，秒级）。

用法（backend 目录下）：
    .venv\\Scripts\\python.exe scripts\\diag_rules.py
改完 data/*.json 后可加 --reload 重新读盘。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import emergency, triage  # noqa: E402
from app.store import reload_data  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acceptance_check import EMERGENCY_CASES, TRIAGE_CASES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true", help="重新读取 data/*.json")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印全部用例")
    args = parser.parse_args()

    if args.reload:
        reload_data()

    hit = 0
    print("=" * 78)
    print("分诊")
    print("=" * 78)
    for text, expect in TRIAGE_CASES:
        card = triage.analyze(text)
        got = card["primary"]["dept"] if card else "（追问）"
        ok = got == expect
        hit += ok
        if not ok or args.verbose:
            flag = "✓" if ok else "✗"
            print(f"{flag} {text}")
            if not ok:
                alts = "、".join(f"{a['dept']}{a['match']}%" for a in (card or {}).get("alternatives", [])) or "-"
                print(f"    期望 {expect} / 实际 {got} / 备选 {alts}")
    acc = hit / len(TRIAGE_CASES) * 100
    print(f"\n分诊准确率 {hit}/{len(TRIAGE_CASES)} = {acc:.1f}%")

    print("\n" + "=" * 78)
    print("急症")
    print("=" * 78)
    emg = 0
    for text in EMERGENCY_CASES:
        payload = emergency.detect(text)
        ok = payload is not None
        emg += ok
        if not ok or args.verbose:
            print(f"{'✓' if ok else '✗'} {text}" + (f"  →  {payload['label']}" if ok else "  （未触发）"))
    rate = emg / len(EMERGENCY_CASES) * 100
    print(f"\n急症识别 {emg}/{len(EMERGENCY_CASES)} = {rate:.1f}%")

    return 0 if acc >= 85 and rate == 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())

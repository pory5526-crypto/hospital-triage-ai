"""小程序静态自检：WXML 标签嵌套、插值配对、JSON 合法性、JS 语法由 node 另行校验。

用法：backend\\.venv\\Scripts\\python.exe scripts\\validate_mp.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MP = ROOT / "miniprogram"

VOID_TAGS = {
    "image", "input", "icon", "progress", "switch", "slider", "textarea", "canvas",
    "video", "audio", "map", "camera", "slot", "wxs", "include", "import", "scroll-view",
}

TAG_RE = re.compile(r"<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>")


def check_wxml(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")

    stack: list[str] = []
    for match in TAG_RE.finditer(text):
        closing, tag, _attrs, self_close = match.groups()
        if self_close == "/" or tag in VOID_TAGS:
            continue
        if closing == "/":
            if not stack or stack[-1] != tag:
                problems.append(f"<{tag}> 闭合不匹配，当前栈 {stack[-3:]}")
                break
            stack.pop()
        else:
            stack.append(tag)
    if stack:
        problems.append(f"未闭合标签 {stack}")

    if text.count("{{") != text.count("}}"):
        problems.append(f"插值括号不配对 {text.count('{{')}/{text.count('}}')}")

    return problems


def main() -> int:
    bad = 0

    for path in sorted(MP.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"✗ JSON {path.relative_to(ROOT)}: {exc}")
            bad += 1

    for path in sorted(MP.rglob("*.wxml")):
        problems = check_wxml(path)
        rel = path.relative_to(ROOT)
        if problems:
            bad += 1
            print(f"✗ {rel}")
            for p in problems:
                print(f"    {p}")
        else:
            print(f"✓ {rel}")

    # WXSS 括号平衡
    for path in sorted(MP.rglob("*.wxss")):
        text = path.read_text(encoding="utf-8")
        depth = 0
        for ch in text:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    break
        if depth != 0:
            bad += 1
            print(f"✗ WXSS {path.relative_to(ROOT)}: 括号不平衡（剩余 {depth}）")
        else:
            print(f"✓ {path.relative_to(ROOT)}")

    print("\n全部通过" if bad == 0 else f"\n{bad} 个文件有问题")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

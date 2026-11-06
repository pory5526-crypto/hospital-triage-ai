"""文件上传 / OCR 冒烟测试。

用法（backend 目录下）：
    .venv\\Scripts\\python.exe scripts\\test_upload.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhl.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def _font(size: int):
    from PIL import ImageFont

    for path in FONTS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_image(lines: list[str]) -> bytes:
    from PIL import Image, ImageDraw

    font = _font(30)
    width, height = 620, 60 + 52 * len(lines)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((30, 30 + index * 52), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_docx(lines: list[str]) -> bytes:
    import docx

    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def upload(client: httpx.Client, name: str, data: bytes) -> dict:
    files = {"file": (name, data, "application/octet-stream")}
    res = client.post(f"{BASE}/api/upload", files=files, timeout=120)
    try:
        return {"status": res.status_code, **res.json()}
    except Exception:  # noqa: BLE001
        return {"status": res.status_code, "raw": res.text[:200]}


def main() -> int:
    ok = True
    with httpx.Client() as client:
        print("=== 1. 图片 OCR（模拟病历）===")
        image = make_image(
            ["患者：王建国  男 58岁", "诊断：高血压2级", "处方：苯磺酸氨氯地平片 5mg 每日一次"]
        )
        res = upload(client, "病历.png", image)
        print("   ", {k: res.get(k) for k in ("status", "ok", "error", "chars")})
        print("    识别文本:", (res.get("text") or "")[:120].replace("\n", " / ") or "(空)")
        if not res.get("ok"):
            ok = False

        print("\n=== 2. Word 文档 ===")
        docx_bytes = make_docx(["检查项目：胸部CT平扫", "检查结论：右肺上叶见小结节，建议3个月后复查"])
        res = upload(client, "检查单.docx", docx_bytes)
        print("   ", {k: res.get(k) for k in ("status", "ok", "error", "chars")})
        print("    识别文本:", (res.get("text") or "")[:120].replace("\n", " / ") or "(空)")
        if not res.get("ok"):
            ok = False

        print("\n=== 3. 不支持的格式 ===")
        res = upload(client, "视频.mp4", b"\x00" * 100)
        print("   ", {"status": res.get("status"), "detail": res.get("detail")})
        if res.get("status") != 415:
            ok = False

        print("\n=== 4. 超过大小限制 ===")
        big = b"\x00" * (11 * 1024 * 1024)
        res = upload(client, "超大.pdf", big)
        print("   ", {"status": res.get("status"), "detail": res.get("detail")})
        if res.get("status") != 413:
            ok = False

        print("\n=== 5. 空白图片（应提示重新上传）===")
        from PIL import Image

        blank = Image.new("RGB", (400, 300), "white")
        buf = io.BytesIO()
        blank.save(buf, format="PNG")
        res = upload(client, "空白.png", buf.getvalue())
        print("   ", {"status": res.get("status"), "ok": res.get("ok"), "error": res.get("error")})
        if res.get("ok"):
            ok = False

    print("\n结果:", "全部通过" if ok else "存在失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

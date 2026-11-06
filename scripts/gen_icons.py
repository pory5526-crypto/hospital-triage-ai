"""生成小程序需要的位图素材（心电波形装饰线）。

网页版用内联 SVG 画的那条心电波，小程序不支持 SVG，这里用 Pillow 光栅化成透明 PNG。
用法：backend/.venv/Scripts/python.exe scripts/gen_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "miniprogram" / "assets"

TEAL = (14, 165, 165, 255)
SCALE = 3  # 超采样倍数，缩回来做抗锯齿


def draw_ecg(width: int, height: int, path: Path) -> None:
    """按原型里的 polyline 走一遍：M0 16 H74 l5 -9 l6 17 l5 -8 H148 l7 -11 l6 15 l5 -4 H232 l6 -8 l5 13 l5 -5 H343"""
    w, h = width * SCALE, height * SCALE
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 原型 viewBox 是 343 x 26，按比例映射
    sx, sy = w / 343.0, h / 26.0
    pts = [(0, 16), (74, 16), (79, 7), (85, 24), (90, 16), (148, 16), (155, 5), (161, 20), (166, 16), (232, 16), (238, 8), (243, 21), (248, 16), (343, 16)]
    scaled = [(x * sx, y * sy) for x, y in pts]
    draw.line(scaled, fill=TEAL, width=max(2, int(1.6 * SCALE)), joint="curve")

    img = img.resize((width, height), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"生成 {path.relative_to(ROOT)}  {width}x{height}")


def main() -> None:
    # 宽度按 343pt × 2 出图（卡片内容宽约 343pt）
    draw_ecg(686, 52, OUT_DIR / "ecg.png")


if __name__ == "__main__":
    main()

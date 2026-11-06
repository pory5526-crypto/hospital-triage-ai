"""文件解析：图片 OCR、PDF 文字、Word 文字。OCR 为可选依赖，缺失时优雅降级。"""

from __future__ import annotations

import io
import threading
from pathlib import Path

from .config import settings


class OcrUnavailable(RuntimeError):
    pass


class OcrFailed(RuntimeError):
    pass


_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as exc:  # noqa: BLE001
            raise OcrUnavailable(
                "图片识别组件未安装。安装方式：pip install -r requirements-ocr.txt"
            ) from exc
        _engine = RapidOCR()
        return _engine


def _ocr_image(data: bytes) -> str:
    import numpy as np
    from PIL import Image

    engine = _get_engine()
    image = Image.open(io.BytesIO(data)).convert("RGB")
    # 长边超过 2000 先缩放，控制耗时
    if max(image.size) > 2000:
        ratio = 2000 / max(image.size)
        image = image.resize((int(image.width * ratio), int(image.height * ratio)))
    result, _ = engine(np.array(image))
    if not result:
        return ""
    lines = [str(item[1]).strip() for item in result if len(item) > 1 and str(item[1]).strip()]
    return "\n".join(lines)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    chunks: list[str] = []
    for page in reader.pages[:10]:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            continue
    return "\n".join(c.strip() for c in chunks if c and c.strip())


def _docx_text(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> tuple[str, str | None]:
    """返回 (文本, 错误说明)。错误说明为 None 表示成功。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_extensions:
        return "", f"不支持的文件格式（{suffix or '未知'}），请上传 JPG/PNG/PDF/Word 文件。"

    kind = settings.allowed_extensions[suffix]
    try:
        if kind == "image":
            text = _ocr_image(data)
        elif kind == "pdf":
            text = _pdf_text(data)
            if len(text.strip()) < 10:
                return "", "这是扫描版 PDF，暂不支持图像型 PDF 识别，请截图后按图片上传。"
        elif kind == "docx":
            text = _docx_text(data)
        else:  # .doc
            return "", "不支持旧版 .doc 格式，请另存为 .docx 或 PDF 后重新上传。"
    except OcrUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        return "", f"文件解析失败：{exc}"

    text = text.strip()
    if len(text) < 4:
        return "", "未能识别文件内容，请重新拍摄上传，或直接文字描述。"
    return text[: settings.ocr_max_chars], None

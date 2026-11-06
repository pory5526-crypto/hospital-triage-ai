"""FastAPI 入口：对话流、上传、配置、埋点、静态前端。"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import asr
from . import tools
from .config import BACKEND_DIR, DISCLAIMER, settings
from .llm import health as llm_health
from .ocr import OcrUnavailable, extract_text
from .pipeline import respond, welcome
from .prompt import invalidate as invalidate_prompt
from .prompt import load_system_prompt, persona_path, stats as prompt_stats
from .rag import kb
from .session import sessions
from .store import get_data, reload_data
from .telemetry import log_event, summary

app = FastAPI(title="医院智能导诊 AI 客服", version="1.0.0")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ 启动
@app.on_event("startup")
async def _startup() -> None:
    data = get_data()
    kb.build(data.knowledge)
    print(
        f"[startup] 科室 {len(data.departments)} 个 · 知识库 {kb.size} 条 · "
        f"医生 {len(data.doctors)} 位 · 分诊规则 {len(data.triage_rules)} 条 · "
        f"LLM {'已配置' if settings.llm_enabled else '未配置（演示模式）'}"
    )


# ------------------------------------------------------------------ 基础
@app.get("/api/health")
async def health() -> dict:
    data = get_data()
    return {
        "status": "ok",
        "departments": len(data.departments),
        "knowledge": kb.size,
        "doctors": len(data.doctors),
        "triageRules": len(data.triage_rules),
        "emergencyRules": len(data.emergency.get("rules", [])),
        "llm": {
            "configured": settings.llm_enabled,
            "model": settings.llm_model or None,
        },
        "sessions": sessions.count,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/api/config")
async def client_config() -> dict:
    data = get_data()
    hospital = data.hospital
    return {
        "hospital": {
            "name": hospital.get("name", settings.hospital_name),
            "address": hospital.get("address", ""),
            "triagePhone": settings.triage_phone,
            "emergencyPhone": settings.emergency_phone,
            "serviceHours": settings.service_hours,
            "afterHoursTip": settings.after_hours_tip,
            "outpatientHours": hospital.get("outpatient_hours", ""),
        },
        "welcome": welcome(),
        "disclaimer": DISCLAIMER,
        "features": {
            "deptSheet": settings.feature_dept_sheet,
            "appointment": settings.feature_appointment,
            "reportReading": settings.feature_report_read,
            "reminder": settings.feature_reminder,
        },
        "upload": {
            "maxMb": settings.max_upload_mb,
            "accept": ".jpg,.jpeg,.png,.webp,.pdf,.docx",
        },
        "quickActions": ["转人工客服", "报告解读", "复诊提醒"],
        "entries": ["症状自查", "科室推荐", "预约挂号", "报告解读"],
    }


@app.get("/api/departments")
async def departments() -> dict:
    data = get_data()
    return {
        "hospital": data.hospital,
        "departments": [
            {
                "name": d["name"],
                "category": d.get("category"),
                "location": d.get("location"),
                "intro": d.get("intro"),
            }
            for d in data.departments
        ],
    }


class SessionRequest(BaseModel):
    channel: str = "miniprogram"


@app.post("/api/session")
async def create_session(req: SessionRequest) -> dict:
    session = sessions.create()
    log_event("session_start", session.id, {"channel": req.channel})
    return {
        "sessionId": session.id,
        "welcome": welcome(),
        "hospital": get_data().hospital.get("name", settings.hospital_name),
    }


# ------------------------------------------------------------------ 对话
class ChatRequest(BaseModel):
    sessionId: str | None = None
    message: str = ""
    imageText: str | None = None
    fileName: str | None = None
    channel: str = "miniprogram"


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    session = sessions.get(req.sessionId)
    if req.sessionId is None:
        log_event("session_start", session.id, {"channel": req.channel})

    async def gen():
        yield _sse({"type": "meta", "sessionId": session.id})
        try:
            async for event in respond(
                session,
                req.message,
                image_text=req.imageText or "",
                file_name=req.fileName or "",
            ):
                yield _sse(event)
        except asyncio.CancelledError:  # 客户端断开
            raise
        except Exception as exc:  # noqa: BLE001
            log_event("error", session.id, {"where": "chat_stream", "error": str(exc)})
            yield _sse({"type": "error", "message": "服务出了点问题，请稍后重试"})
            yield _sse({"type": "done", "latencyMs": 0})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------ 上传
@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式（{suffix or '未知'}），请上传 JPG/PNG/PDF/Word 文件。",
        )

    raw = await file.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise HTTPException(
            status_code=413, detail=f"文件超过 {settings.max_upload_mb}MB 限制，请压缩后重试。"
        )
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空，请重新上传。")

    session_id = request.headers.get("x-session-id", "")
    stored = settings.runtime_upload_dir / f"{uuid.uuid4().hex}{suffix}"
    try:
        stored.write_bytes(raw)
    except OSError:
        pass

    log_event("file_upload", session_id, {"name": file.filename, "size": len(raw)})

    try:
        text, error = extract_text(file.filename or "", raw)
    except OcrUnavailable as exc:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "fileName": file.filename,
                "text": "",
                "error": "图片识别功能尚未启用，请直接文字描述症状，或上传 PDF/Word 文件。",
                "hint": str(exc),
            },
        )

    if error:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "fileName": file.filename, "text": "", "error": error},
        )

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "fileName": file.filename,
            "text": text,
            "chars": len(text),
            "error": None,
        },
    )


# ------------------------------------------------------------------ 知识库 / 工具
@app.get("/api/kb/search")
async def kb_search(q: str, topK: int = 4) -> dict:
    hits = kb.retrieve(q, top_k=topK, min_confidence=0.05)
    return {
        "query": q,
        "hits": [
            {
                "id": h.item.get("id"),
                "title": h.item.get("title"),
                "content": h.item.get("content"),
                "category": h.item.get("category"),
                "confidence": h.confidence,
            }
            for h in hits
        ],
    }


@app.get("/api/tools/department")
async def tool_department(name: str) -> dict:
    return {"result": tools.query_department(name)}


# ------------------------------------------------------------------ 语音识别
@app.post("/api/asr")
async def asr_transcribe(file: UploadFile = File(...)) -> JSONResponse:
    """语音转文字：小程序 RecorderManager 录的音频传上来，返回识别文字。"""
    raw = await file.read()
    suffix = Path(file.filename or "audio.mp3").suffix.lstrip(".").lower() or "mp3"
    text, error = await asr.transcribe(raw, suffix)
    log_event("voice_asr", "", {"ok": bool(text), "chars": len(text), "size": len(raw)})
    return JSONResponse(
        status_code=200,
        content={"ok": bool(text), "text": text, "error": error},
    )


@app.get("/api/tools/schedule")
async def tool_schedule(dept: str = "", weekday: int | None = None) -> dict:
    return {"result": tools.query_doctor_schedule(dept, weekday)}


# ------------------------------------------------------------------ 埋点与运维
class FrontendEvent(BaseModel):
    sessionId: str = ""
    event: str
    payload: dict = Field(default_factory=dict)


@app.post("/api/events")
async def collect_event(evt: FrontendEvent) -> dict:
    allowed = {
        "session_end",
        "dept_entry_click",
        "quick_action_click",
        "retry",
        "upload_click",
        "voice_start",
        "voice_error",
        "ui_error",
    }
    if evt.event in allowed:
        log_event(evt.event, evt.sessionId, evt.payload)
    return {"ok": True}


@app.get("/api/metrics/summary")
async def metrics() -> dict:
    return summary()


@app.get("/api/llm/health")
async def llm_status() -> dict:
    return await llm_health()


@app.post("/api/admin/reload")
async def admin_reload() -> dict:
    """热加载数据文件与系统提示词（改完 JSON / persona.md 不用重启）。"""
    data = reload_data()
    kb.build(data.knowledge)
    invalidate_prompt()
    return {
        "ok": True,
        "departments": len(data.departments),
        "knowledge": kb.size,
        "doctors": len(data.doctors),
        "prompt": prompt_stats(),
    }


class PromptPayload(BaseModel):
    text: str


@app.get("/api/admin/prompt")
async def get_prompt() -> dict:
    """查看当前生效的系统提示词。"""
    return {"text": load_system_prompt(), **prompt_stats()}


@app.put("/api/admin/prompt")
async def put_prompt(payload: PromptPayload) -> dict:
    """直接替换系统提示词（写回 persona.md，立即生效）。"""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="提示词不能为空")
    persona_path().write_text(payload.text, encoding="utf-8")
    invalidate_prompt()
    return {"ok": True, **prompt_stats()}


# ------------------------------------------------------------------ 静态前端
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{path:path}")
    async def spa(path: str) -> FileResponse:
        target = FRONTEND_DIST / path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")

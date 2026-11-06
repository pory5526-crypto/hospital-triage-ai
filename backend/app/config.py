"""全局配置。所有配置项都可以用环境变量覆盖，前缀 HOSPITAL_。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "app" / "data"
RUNTIME_DIR = BACKEND_DIR / "runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
LOG_DIR = RUNTIME_DIR / "logs"

# 加载 backend/.env（不存在则忽略）
try:  # pragma: no cover
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except Exception:  # noqa: BLE001
    pass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"HOSPITAL_{key}", os.environ.get(key, default)).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


@dataclass
class Settings:
    # ---------- 医院信息 ----------
    hospital_name: str = field(default_factory=lambda: _env("HOSPITAL_NAME", "协和医院"))
    hospital_short: str = field(default_factory=lambda: _env("HOSPITAL_SHORT", "协和医院"))
    triage_phone: str = field(default_factory=lambda: _env("TRIAGE_PHONE", "010-69156114"))
    emergency_phone: str = field(default_factory=lambda: _env("EMERGENCY_PHONE", "010-69155120"))
    service_hours: str = field(
        default_factory=lambda: _env("SERVICE_HOURS", "工作日 7:30–17:00 · 周六 8:00–12:00")
    )
    after_hours_tip: str = field(
        default_factory=lambda: _env(
            "AFTER_HOURS_TIP", "非人工服务时间请前往门诊楼 1F 导诊台，急诊请直接到急诊楼 1F。"
        )
    )

    # ---------- 大模型（OpenAI 兼容协议）----------
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", ""))
    # "true"/"false" 会作为 Qwen 的 enable_thinking 参数下发；留空则不下发
    llm_enable_thinking: str = field(default_factory=lambda: _env("LLM_ENABLE_THINKING", ""))

    # ---------- 语音识别（可选，小程序端语音输入用）----------
    asr_model: str = field(default_factory=lambda: _env("ASR_MODEL", "qwen-audio-3.1-asr-flash"))
    asr_url: str = field(default_factory=lambda: _env("ASR_URL", ""))
    llm_timeout: float = field(default_factory=lambda: _env_float("LLM_TIMEOUT", 25.0))
    llm_max_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 800))
    llm_temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.3))
    enable_tool_calling: bool = field(default_factory=lambda: _env_bool("ENABLE_TOOL_CALLING", True))

    # ---------- RAG ----------
    rag_top_k: int = field(default_factory=lambda: _env_int("RAG_TOP_K", 4))
    rag_min_score: float = field(default_factory=lambda: _env_float("RAG_MIN_SCORE", 0.18))

    # ---------- 上传 ----------
    max_upload_mb: int = field(default_factory=lambda: _env_int("MAX_UPLOAD_MB", 10))
    ocr_max_chars: int = field(default_factory=lambda: _env_int("OCR_MAX_CHARS", 1800))

    # ---------- 会话 ----------
    max_history_turns: int = field(default_factory=lambda: _env_int("MAX_HISTORY_TURNS", 12))
    session_ttl_seconds: int = field(default_factory=lambda: _env_int("SESSION_TTL_SECONDS", 7200))

    # ---------- 特性开关（V1 / V2 占位）----------
    feature_dept_sheet: bool = field(default_factory=lambda: _env_bool("FEATURE_DEPT_SHEET", False))
    feature_appointment: bool = field(default_factory=lambda: _env_bool("FEATURE_APPOINTMENT", False))
    feature_report_read: bool = field(default_factory=lambda: _env_bool("FEATURE_REPORT_READ", False))
    feature_reminder: bool = field(default_factory=lambda: _env_bool("FEATURE_REMINDER", False))

    # ---------- 安全 ----------
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "*"))

    @property
    def allowed_extensions(self) -> dict[str, str]:
        return {
            ".jpg": "image",
            ".jpeg": "image",
            ".png": "image",
            ".webp": "image",
            ".bmp": "image",
            ".pdf": "pdf",
            ".docx": "docx",
            ".doc": "doc",
        }

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @property
    def runtime_upload_dir(self) -> Path:
        return UPLOAD_DIR

    @property
    def runtime_log_dir(self) -> Path:
        return LOG_DIR

    def ensure_dirs(self) -> None:
        for d in (DATA_DIR, RUNTIME_DIR, UPLOAD_DIR, LOG_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()

DISCLAIMER = (
    "我是医院智能导诊助手，仅提供科室推荐与就诊流程指引，不能替代医生诊断。"
    "具体病情请以医生面诊判断为准。"
)

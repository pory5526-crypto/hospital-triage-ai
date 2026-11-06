"""埋点与审计：写 JSONL 日志，并提供内存汇总，对应 PRD「六、交付设计」的 V1 五类埋点。"""

from __future__ import annotations

import json
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from .config import LOG_DIR

_LOCK = threading.Lock()
_COUNTER: Counter[str] = Counter()
_RESPONSE_TIMES: list[float] = []
_SESSION_IDS: set[str] = set()
_HANDOFF_SESSIONS: set[str] = set()

KNOWN_EVENTS = {
    "session_start",
    "session_end",
    "message_sent",
    "triage_shown",
    "emergency_triggered",
    "handoff",
    "error",
    "file_upload",
}


def _log_path() -> Path:
    day = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"events-{day}.jsonl"


def log_event(event: str, session_id: str = "", payload: dict | None = None) -> None:
    record = {
        "ts": round(time.time(), 3),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "session_id": session_id,
        "payload": payload or {},
    }
    with _LOCK:
        _COUNTER[event] += 1
        try:
            with _log_path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
        if event == "session_start":
            _SESSION_IDS.add(session_id)
        if event == "handoff":
            _HANDOFF_SESSIONS.add(session_id)


def record_latency(seconds: float) -> None:
    with _LOCK:
        _RESPONSE_TIMES.append(seconds)
        if len(_RESPONSE_TIMES) > 500:
            del _RESPONSE_TIMES[:-500]


def summary() -> dict:
    with _LOCK:
        sessions_total = max(len(_SESSION_IDS), _COUNTER.get("session_start", 0))
        handoffs = len(_HANDOFF_SESSIONS)
        avg_latency = (sum(_RESPONSE_TIMES) / len(_RESPONSE_TIMES)) if _RESPONSE_TIMES else 0.0
        return {
            "sessions": sessions_total,
            "messages": _COUNTER.get("message_sent", 0),
            "triage_shown": _COUNTER.get("triage_shown", 0),
            "emergency_triggered": _COUNTER.get("emergency_triggered", 0),
            "handoff": handoffs,
            "handoff_rate": round(handoffs / sessions_total, 4) if sessions_total else 0.0,
            "errors": _COUNTER.get("error", 0),
            "avg_response_ms": round(avg_latency * 1000),
            "events": dict(_COUNTER),
        }

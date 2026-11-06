"""会话管理：内存存储 + TTL 清理，保留多轮上下文。"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from .config import settings


@dataclass
class Turn:
    role: str  # user / assistant
    content: str
    ts: float = field(default_factory=time.time)
    kind: str = "text"  # text / triage / emergency / file


@dataclass
class Session:
    id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: list[Turn] = field(default_factory=list)
    # 分诊上下文：用于第二轮补充症状时合并判断
    last_triage: dict | None = None
    awaiting_clarify: bool = False
    emergency_locked: bool = False
    fail_streak: int = 0
    handoff_shown: bool = False

    def history_for_llm(self) -> list[dict]:
        turns = self.turns[-settings.max_history_turns * 2 :]
        return [{"role": t.role, "content": t.content} for t in turns if t.content]

    def add(self, role: str, content: str, kind: str = "text") -> None:
        self.turns.append(Turn(role=role, content=content, kind=kind))
        self.updated_at = time.time()
        if len(self.turns) > 80:
            self.turns = self.turns[-60:]

    def recent_user_text(self, limit: int = 3) -> str:
        texts = [t.content for t in self.turns if t.role == "user"][-limit:]
        return "；".join(texts)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = Session(id=uuid.uuid4().hex[:16])
        with self._lock:
            self._sessions[session.id] = session
        self.purge()
        return session

    def get(self, session_id: str | None) -> Session:
        if session_id:
            with self._lock:
                found = self._sessions.get(session_id)
                if found:
                    found.updated_at = time.time()
                    return found
        return self.create()

    def purge(self) -> None:
        cutoff = time.time() - settings.session_ttl_seconds
        with self._lock:
            stale = [sid for sid, s in self._sessions.items() if s.updated_at < cutoff]
            for sid in stale:
                self._sessions.pop(sid, None)

    @property
    def count(self) -> int:
        return len(self._sessions)


sessions = SessionStore()

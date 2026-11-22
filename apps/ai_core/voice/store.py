"""Process-local mock session store.

One active session per user, bounded size, strict expiry. Every state change runs under one
lock, so acquire/release are atomic within a process. A shared Redis store (keys under
config.NAMESPACE) is intentionally not part of PR 1.
"""
from __future__ import annotations

import math
import threading
import time
import uuid
from dataclasses import dataclass

from .config import MAX_EVENTS_PER_SESSION, MAX_SESSIONS, NAMESPACE


@dataclass(frozen=True)
class VoiceSession:
    id: str
    user_id: int
    conversation_id: str | None
    expires_at: float


class SessionBusy(Exception):
    """The user already has an active session; retry_after is computed under the lock."""

    def __init__(self, retry_after):
        super().__init__("session active")
        self.retry_after = retry_after


class StoreFull(Exception):
    def __init__(self, retry_after):
        super().__init__("store full")
        self.retry_after = retry_after


class EventLimit(Exception):
    pass


def user_key(user_id: int) -> str:
    return "{}:session:{}".format(NAMESPACE, int(user_id))


class VoiceSessionStore:
    def __init__(self, max_sessions=MAX_SESSIONS):
        self._lock = threading.Lock()
        self._sessions = {}
        self._by_user = {}
        self._events = {}
        self._max = max_sessions

    def _drop(self, session):
        self._sessions.pop(session.id, None)
        self._events.pop(session.id, None)
        if self._by_user.get(session.user_id) == session.id:
            del self._by_user[session.user_id]

    def _purge(self, now):
        for session in [s for s in self._sessions.values() if s.expires_at <= now]:
            self._drop(session)

    @staticmethod
    def _remaining(expires_at, now):
        return max(1, math.ceil(expires_at - now))

    def acquire(self, user_id, conversation_id, ttl_seconds):
        with self._lock:
            now = time.monotonic()
            self._purge(now)
            existing = self._by_user.get(user_id)
            if existing:
                raise SessionBusy(self._remaining(self._sessions[existing].expires_at, now))
            if len(self._sessions) >= self._max:
                soonest = min(s.expires_at for s in self._sessions.values())
                raise StoreFull(self._remaining(soonest, now))
            session = VoiceSession(
                id=str(uuid.uuid4()), user_id=user_id,
                conversation_id=conversation_id, expires_at=now + ttl_seconds,
            )
            self._sessions[session.id] = session
            self._by_user[user_id] = session.id
            self._events[session.id] = 0
            return session

    def get(self, session_id, user_id):
        with self._lock:
            self._purge(time.monotonic())
            session = self._sessions.get(session_id)
            return session if session is not None and session.user_id == user_id else None

    def record_event(self, session_id, user_id):
        with self._lock:
            self._purge(time.monotonic())
            session = self._sessions.get(session_id)
            if session is None or session.user_id != user_id:
                return None
            if self._events[session_id] >= MAX_EVENTS_PER_SESSION:
                raise EventLimit()
            self._events[session_id] += 1
            return session

    def release(self, session_id, user_id):
        """Atomic: exactly one caller wins; others (and non-owners) get False."""
        with self._lock:
            self._purge(time.monotonic())
            session = self._sessions.get(session_id)
            if session is None or session.user_id != user_id:
                return False
            self._drop(session)
            return True

    def clear(self):
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            self._by_user.clear()
            self._events.clear()
            return count


_store = VoiceSessionStore()


def get_store() -> VoiceSessionStore:
    return _store


def reset_store() -> None:
    _store.clear()

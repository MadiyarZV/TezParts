"""SQLite-хранилище: связка «чат Telegram → сессия Claude» и журнал расходов.

Одна таблица на маппинг, одна на историю. Больше пока не нужно —
сама история диалога живёт внутри сессии Agent SDK, дублировать её незачем.
"""
from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    chat_id     INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    session_id  TEXT,
    cost_usd    REAL,
    turns       INTEGER,
    duration_ms INTEGER,
    ok          INTEGER NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Storage:
    def __init__(self, path: Path) -> None:
        self._path = str(path)
        self._lock = asyncio.Lock()
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    async def _run(self, fn, *args):
        async with self._lock:
            return await asyncio.to_thread(fn, *args)

    # --- сессии ---

    def _get_session(self, chat_id: int) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT session_id FROM chat_sessions WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return row["session_id"] if row else None

    async def get_session(self, chat_id: int) -> str | None:
        return await self._run(self._get_session, chat_id)

    def _set_session(self, chat_id: int, session_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO chat_sessions (chat_id, session_id, updated_at) "
                "VALUES (?, ?, datetime('now')) "
                "ON CONFLICT(chat_id) DO UPDATE SET "
                "session_id = excluded.session_id, updated_at = excluded.updated_at",
                (chat_id, session_id),
            )
            conn.commit()

    async def set_session(self, chat_id: int, session_id: str) -> None:
        await self._run(self._set_session, chat_id, session_id)

    def _clear_session(self, chat_id: int) -> None:
        with closing(self._connect()) as conn:
            conn.execute("DELETE FROM chat_sessions WHERE chat_id = ?", (chat_id,))
            conn.commit()

    async def clear_session(self, chat_id: int) -> None:
        await self._run(self._clear_session, chat_id)

    # --- расходы ---

    def _log_run(self, chat_id, user_id, session_id, cost, turns, duration, ok) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO runs (chat_id, user_id, session_id, cost_usd, turns, "
                "duration_ms, ok) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chat_id, user_id, session_id, cost, turns, duration, int(ok)),
            )
            conn.commit()

    async def log_run(self, **kwargs) -> None:
        await self._run(
            self._log_run,
            kwargs["chat_id"],
            kwargs["user_id"],
            kwargs.get("session_id"),
            kwargs.get("cost_usd"),
            kwargs.get("turns"),
            kwargs.get("duration_ms"),
            kwargs.get("ok", True),
        )

    def _stats(self, chat_id: int, days: int) -> dict:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(cost_usd), 0) AS total "
                "FROM runs WHERE chat_id = ? AND created_at >= datetime('now', ?)",
                (chat_id, f"-{days} days"),
            ).fetchone()
        return {"runs": row["n"], "cost_usd": row["total"]}

    async def stats(self, chat_id: int, days: int = 30) -> dict:
        return await self._run(self._stats, chat_id, days)

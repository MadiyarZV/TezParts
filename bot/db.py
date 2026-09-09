"""Хранилище черновиков.

Состояние живёт здесь, а не в контексте модели: агент запускается stateless,
каждый прогон получает ровно тот кусок, который ему нужен. Так бота можно
отлаживать и переживать рестарты без потери работы.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    platform    TEXT    NOT NULL DEFAULT 'threads',
    topic       TEXT    NOT NULL,
    text        TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'draft',  -- draft | approved | rejected | published
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS drafts_user_status ON drafts (user_id, status);
"""


@dataclass
class Draft:
    id: int
    user_id: int
    platform: str
    topic: str
    text: str
    status: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def add_draft(self, user_id: int, topic: str, text: str, platform: str = "threads") -> int:
        cur = self._conn.execute(
            "INSERT INTO drafts (user_id, platform, topic, text, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, platform, topic, text, _now(), _now()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_draft(self, draft_id: int) -> Draft | None:
        row = self._conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        return self._row_to_draft(row) if row else None

    def set_status(self, draft_id: int, status: str) -> None:
        self._conn.execute(
            "UPDATE drafts SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), draft_id),
        )
        self._conn.commit()

    def list_drafts(self, user_id: int, status: str = "draft", limit: int = 10) -> list[Draft]:
        rows = self._conn.execute(
            "SELECT * FROM drafts WHERE user_id = ? AND status = ?"
            " ORDER BY id DESC LIMIT ?",
            (user_id, status, limit),
        ).fetchall()
        return [self._row_to_draft(r) for r in rows]

    @staticmethod
    def _row_to_draft(row: sqlite3.Row) -> Draft:
        return Draft(
            id=row["id"],
            user_id=row["user_id"],
            platform=row["platform"],
            topic=row["topic"],
            text=row["text"],
            status=row["status"],
        )

"""Конфигурация из переменных окружения. Падаем на старте, а не в рантайме."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задана переменная окружения {name}. Смотри .env.example")
    return value


def _int_set(name: str) -> set[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        raise RuntimeError(
            f"{name} пуст. Без белого списка бот с доступом к shell открыт всему интернету."
        )
    return {int(part.strip()) for part in raw.split(",") if part.strip()}


@dataclass(frozen=True)
class Config:
    telegram_token: str = field(default_factory=lambda: _require("TELEGRAM_BOT_TOKEN"))
    allowed_user_ids: frozenset[int] = field(
        default_factory=lambda: frozenset(_int_set("ALLOWED_USER_IDS"))
    )
    model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-5"))
    effort: str = field(default_factory=lambda: os.getenv("CLAUDE_EFFORT", "high"))
    workspace: Path = field(
        default_factory=lambda: Path(os.getenv("AGENT_WORKSPACE", "./workspace")).resolve()
    )
    db_path: Path = field(default_factory=lambda: Path(os.getenv("DB_PATH", "./bot.db")).resolve())
    max_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MAX_BUDGET_USD", "2.0"))
    )
    max_turns: int = field(default_factory=lambda: int(os.getenv("MAX_TURNS", "60")))

    def __post_init__(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


config = Config()

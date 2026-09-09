import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _ids(raw: str) -> set[int]:
    return {int(x) for x in raw.replace(" ", "").split(",") if x}


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_ids: set[int]
    model: str
    workspace: Path
    db_path: Path
    publisher: str
    publora_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

        allowed = _ids(os.environ.get("ALLOWED_USER_IDS", ""))
        if not allowed:
            # Бот с доступом к API-ключу и публикации не должен быть открыт всем.
            raise RuntimeError("ALLOWED_USER_IDS не задан — бот отказывается стартовать")

        return cls(
            bot_token=token,
            allowed_user_ids=allowed,
            model=os.environ.get("CLAUDE_MODEL", "claude-opus-5"),
            workspace=Path(os.environ.get("AGENT_WORKSPACE", "./workspace")).resolve(),
            db_path=Path(os.environ.get("DB_PATH", "./data/bot.db")).resolve(),
            publisher=os.environ.get("PUBLISHER", "manual"),
            publora_api_key=os.environ.get("PUBLORA_API_KEY", ""),
        )

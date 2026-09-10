"""Обёртка над Claude Agent SDK.

Одна функция: прогнать запрос через агента и отдать текст + метаданные.
Прогресс отдаётся через колбэк, чтобы Telegram-слой мог показывать,
чем агент занят прямо сейчас, — иначе пользователь три минуты смотрит в пустоту.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from bot.config import config

log = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None]]


@dataclass
class AgentResult:
    text: str
    session_id: str | None
    cost_usd: float | None
    turns: int | None
    duration_ms: int | None
    is_error: bool = False


def _build_options(session_id: str | None) -> ClaudeAgentOptions:
    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        # Читаем скилы и настройки с диска — ради них всё и затевалось.
        setting_sources=["user", "project"],
        # Спросить разрешение не у кого: на том конце Telegram, а не терминал.
        # Единственная защита — белый список пользователей и изоляция контейнера.
        permission_mode="bypassPermissions",
        cwd=str(config.workspace),
        model=config.model,
        effort=config.effort,
        max_turns=config.max_turns,
        max_budget_usd=config.max_budget_usd,
    )
    if session_id:
        options.resume = session_id
    return options


def _describe(block) -> str | None:
    """Короткое описание действия агента для строки прогресса."""
    name = getattr(block, "name", None)
    if not name:
        return None
    args = getattr(block, "input", None) or {}
    detail = ""
    for key in ("file_path", "command", "pattern", "path", "url", "skill"):
        value = args.get(key)
        if isinstance(value, str) and value:
            detail = value if len(value) <= 60 else value[:57] + "..."
            break
    return f"{name}: {detail}" if detail else str(name)


async def run_agent(
    prompt: str,
    session_id: str | None,
    on_progress: ProgressCallback | None = None,
) -> AgentResult:
    chunks: list[str] = []
    result_session: str | None = session_id
    cost = turns = duration = None
    is_error = False

    async for message in query(prompt=prompt, options=_build_options(session_id)):
        # session_id приходит в системном сообщении инициализации; при
        # старте новой сессии он отличается от переданного на resume.
        found = getattr(message, "session_id", None)
        if found:
            result_session = found

        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
                elif on_progress:
                    described = _describe(block)
                    if described:
                        await on_progress(described)

        elif isinstance(message, ResultMessage):
            cost = getattr(message, "total_cost_usd", None)
            turns = getattr(message, "num_turns", None)
            duration = getattr(message, "duration_ms", None)
            is_error = bool(getattr(message, "is_error", False))
            # ResultMessage.result содержит финальный текст; берём его,
            # если по какой-то причине текстовых блоков не было.
            final = getattr(message, "result", None)
            if final and not chunks:
                chunks.append(str(final))

    text = "\n\n".join(part.strip() for part in chunks if part and part.strip())
    if not text:
        text = "Агент завершил работу, но ничего не ответил."
        is_error = True

    return AgentResult(
        text=text,
        session_id=result_session,
        cost_usd=cost,
        turns=turns,
        duration_ms=duration,
        is_error=is_error,
    )

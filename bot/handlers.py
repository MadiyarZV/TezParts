"""Telegram-слой: команды, доступ, отправка ответов."""
from __future__ import annotations

import asyncio
import logging
import time

from aiogram import BaseMiddleware, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.agent import run_agent
from bot.config import config
from bot.formatting import render
from bot.runner import ChatQueue
from bot.storage import Storage

log = logging.getLogger(__name__)

router = Router()
queue = ChatQueue()
storage = Storage(config.db_path)

PROGRESS_INTERVAL = 3.0  # чаще Telegram начнёт резать по rate limit


class AccessMiddleware(BaseMiddleware):
    """Белый список. Бот имеет shell на сервере — это не опциональная защита."""

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None or user.id not in config.allowed_user_ids:
            if isinstance(event, Message):
                log.warning("Отказ в доступе: user_id=%s", getattr(user, "id", None))
                await event.answer(f"Доступ закрыт. Твой ID: {getattr(user, 'id', '?')}")
            return None
        return await handler(event, data)


router.message.middleware(AccessMiddleware())


async def _send_long(message: Message, text: str) -> None:
    for part in render(text):
        try:
            await message.answer(part, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            log.exception("Не удалось отправить как HTML, шлём как текст")
            await message.answer(part, disable_web_page_preview=True)
        await asyncio.sleep(0.05)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Claude на связи. Пиши задачу обычным текстом — я работаю в постоянной "
        "рабочей папке на сервере, со скилами и доступом к файлам.\n\n"
        "/new — начать разговор с чистого листа\n"
        "/stop — прервать текущую задачу\n"
        "/cost — расходы за 30 дней\n"
        "/status — что происходит прямо сейчас"
    )


@router.message(Command("new"))
async def cmd_new(message: Message) -> None:
    await storage.clear_session(message.chat.id)
    await message.answer("Контекст сброшен. Следующее сообщение начнёт новую сессию.")


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    dropped = queue.drain(message.chat.id)
    cancelled = queue.cancel_current(message.chat.id)
    if cancelled or dropped:
        await message.answer(f"Остановлено. Снято из очереди: {dropped}.")
    else:
        await message.answer("Нечего останавливать.")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    chat_id = message.chat.id
    session = await storage.get_session(chat_id)
    await message.answer(
        f"Занят: {'да' if queue.is_busy(chat_id) else 'нет'}\n"
        f"В очереди: {queue.pending(chat_id)}\n"
        f"Сессия: {session or 'новая'}\n"
        f"Модель: {config.model} (effort={config.effort})"
    )


@router.message(Command("cost"))
async def cmd_cost(message: Message) -> None:
    stats = await storage.stats(message.chat.id, days=30)
    await message.answer(
        f"За 30 дней: {stats['runs']} запросов, ${stats['cost_usd']:.2f}.\n"
        f"Лимит на один запрос: ${config.max_budget_usd:.2f}."
    )


@router.message(F.text)
async def handle_text(message: Message) -> None:
    prompt = (message.text or "").strip()
    if not prompt:
        return

    position = queue.pending(message.chat.id) + (1 if queue.is_busy(message.chat.id) else 0)
    if position:
        await message.answer(f"Принял, ты {position}-й в очереди этого чата.")

    await queue.submit(message.chat.id, lambda: _process(message, prompt))


async def _process(message: Message, prompt: str) -> None:
    chat_id = message.chat.id
    started = time.monotonic()
    status = await message.answer("⏳ Работаю…")
    last_edit = 0.0
    typing_task = asyncio.create_task(_keep_typing(message))

    async def on_progress(action: str) -> None:
        nonlocal last_edit
        now = time.monotonic()
        if now - last_edit < PROGRESS_INTERVAL:
            return
        last_edit = now
        elapsed = int(now - started)
        try:
            await status.edit_text(f"⏳ {elapsed}с · {action}")
        except Exception:
            pass  # «message is not modified» и прочий шум Telegram

    session_id = await storage.get_session(chat_id)
    try:
        result = await run_agent(prompt, session_id, on_progress)
    except asyncio.CancelledError:
        await _safe_delete(status)
        await message.answer("Задача прервана.")
        raise
    except Exception as error:
        log.exception("Агент упал")
        await _safe_delete(status)
        await message.answer(f"Ошибка: {type(error).__name__}: {error}")
        await storage.log_run(chat_id=chat_id, user_id=message.from_user.id, ok=False)
        return
    finally:
        typing_task.cancel()

    if result.session_id:
        await storage.set_session(chat_id, result.session_id)
    await storage.log_run(
        chat_id=chat_id,
        user_id=message.from_user.id,
        session_id=result.session_id,
        cost_usd=result.cost_usd,
        turns=result.turns,
        duration_ms=result.duration_ms,
        ok=not result.is_error,
    )

    await _safe_delete(status)
    await _send_long(message, result.text)


async def _keep_typing(message: Message) -> None:
    """Telegram гасит индикатор через 5 секунд, поэтому обновляем его сами."""
    try:
        while True:
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.debug("Не удалось отправить chat action", exc_info=True)


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass

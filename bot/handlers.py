import html
import logging

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)

from bot.agent import ContentAgent
from bot.db import Storage
from bot.publishers import Publisher
from bot.worker import JobQueue

log = logging.getLogger(__name__)
router = Router()


class WhitelistMiddleware(BaseMiddleware):
    """Единственный контур авторизации. У бота есть API-ключ и право публикации,
    поэтому whitelist стоит с первого коммита, а не 'потом добавим'."""

    def __init__(self, allowed: set[int]):
        self.allowed = allowed

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if user is None or user.id not in self.allowed:
            log.warning("отклонён доступ: user_id=%s", getattr(user, "id", None))
            return None
        return await handler(event, data)


def _draft_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Опубликовать", callback_data=f"pub:{draft_id}"),
                InlineKeyboardButton(text="Переписать", callback_data=f"redo:{draft_id}"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"rej:{draft_id}"),
            ]
        ]
    )


def _fmt(text: str) -> str:
    return f"<pre>{html.escape(text)}</pre>"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Панель управления контентом @tez.parts.\n\n"
        "/post <тема> — черновик поста для Threads\n"
        "/drafts — черновики, ждущие решения\n"
        "/ping — проверка живости"
    )


@router.message(Command("ping"))
async def cmd_ping(message: Message, queue: JobQueue) -> None:
    await message.answer(f"жив. задач в очереди: {queue.pending}")


@router.message(Command("post"))
async def cmd_post(
    message: Message, command: CommandObject, queue: JobQueue, agent: ContentAgent, storage: Storage
) -> None:
    topic = (command.args or "").strip()
    if not topic:
        await message.answer("Нужна тема: /post замена бампера на Camry 70")
        return

    async def job() -> None:
        status = await message.answer("Пишу...")
        try:
            text = await agent.write_post(topic)
        except Exception as exc:
            log.exception("генерация поста упала")
            await status.edit_text(f"Не получилось: {exc}")
            return
        draft_id = storage.add_draft(message.from_user.id, topic, text)
        await status.delete()
        await message.answer(
            _fmt(text), parse_mode="HTML", reply_markup=_draft_keyboard(draft_id)
        )

    if not await queue.put(job):
        await message.answer("Очередь забита, попробуйте позже.")
        return
    if queue.pending > 1:
        await message.answer(f"В очереди, впереди задач: {queue.pending - 1}")


@router.message(Command("drafts"))
async def cmd_drafts(message: Message, storage: Storage) -> None:
    drafts = storage.list_drafts(message.from_user.id)
    if not drafts:
        await message.answer("Черновиков нет.")
        return
    for draft in drafts:
        await message.answer(
            _fmt(draft.text), parse_mode="HTML", reply_markup=_draft_keyboard(draft.id)
        )


@router.callback_query(F.data.startswith("pub:"))
async def cb_publish(
    callback: CallbackQuery, storage: Storage, publisher: Publisher
) -> None:
    draft_id = int(callback.data.split(":", 1)[1])
    draft = storage.get_draft(draft_id)
    if draft is None or draft.user_id != callback.from_user.id:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    storage.set_status(draft_id, "approved")
    result = await publisher.publish(draft.platform, draft.text)
    if result.ok:
        storage.set_status(draft_id, "published")

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(result.message + (f"\n{result.url}" if result.url else ""))
    await callback.answer()


@router.callback_query(F.data.startswith("rej:"))
async def cb_reject(callback: CallbackQuery, storage: Storage) -> None:
    draft_id = int(callback.data.split(":", 1)[1])
    draft = storage.get_draft(draft_id)
    if draft is None or draft.user_id != callback.from_user.id:
        await callback.answer("Черновик не найден", show_alert=True)
        return
    storage.set_status(draft_id, "rejected")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отклонено")


@router.callback_query(F.data.startswith("redo:"))
async def cb_rewrite(callback: CallbackQuery) -> None:
    draft_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer(
        f"Ответьте на это сообщение правкой в формате:\n/fix {draft_id} <что поменять>"
    )
    await callback.answer()


@router.message(Command("fix"))
async def cmd_fix(
    message: Message, command: CommandObject, queue: JobQueue, agent: ContentAgent, storage: Storage
) -> None:
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) < 2 or not args[0].isdigit():
        await message.answer("Формат: /fix <id> <что поменять>")
        return

    draft_id, feedback = int(args[0]), args[1]
    draft = storage.get_draft(draft_id)
    if draft is None or draft.user_id != message.from_user.id:
        await message.answer("Черновик не найден")
        return

    async def job() -> None:
        status = await message.answer("Переписываю...")
        try:
            text = await agent.rewrite_post(draft.text, feedback)
        except Exception as exc:
            log.exception("переписывание упало")
            await status.edit_text(f"Не получилось: {exc}")
            return
        storage.set_status(draft_id, "rejected")
        new_id = storage.add_draft(message.from_user.id, draft.topic, text, draft.platform)
        await status.delete()
        await message.answer(
            _fmt(text), parse_mode="HTML", reply_markup=_draft_keyboard(new_id)
        )

    if not await queue.put(job):
        await message.answer("Очередь забита, попробуйте позже.")

from aiogram import Router
from aiogram.types import CallbackQuery

from bot.ai.content_generator import regenerate_draft
from bot.db.models import Post, PostStatus
from bot.db.session import get_session
from bot.jobs.daily_post import draft_keyboard

router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("use:"))
async def on_use(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        post = await session.get(Post, post_id)
        if post:
            post.status = PostStatus.USED
            await session.commit()
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ Взято в публикацию")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("discard:"))
async def on_discard(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        post = await session.get(Post, post_id)
        if post:
            post.status = PostStatus.DISCARDED
            await session.commit()
    await callback.message.edit_text(f"{callback.message.text}\n\n🗑 Отклонено")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("regen:"))
async def on_regen(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        post = await session.get(Post, post_id)
        if not post:
            await callback.answer("Черновик не найден")
            return
        new_text = await regenerate_draft(post.idea_title, post.idea_angle or "", post.content)
        post.content = new_text
        await session.commit()

    await callback.message.edit_text(
        f"📝 Черновик поста\n\n{new_text}\n\n— идея: {post.idea_title}",
        reply_markup=draft_keyboard(post_id),
    )
    await callback.answer("Готово, другой вариант")

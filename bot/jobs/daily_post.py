from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.ai.content_generator import generate_draft, generate_idea
from bot.config import settings
from bot.db.models import ContentIdea, IdeaStatus, Post, PostStatus
from bot.db.session import get_session


def draft_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Другой вариант", callback_data=f"regen:{post_id}"),
                InlineKeyboardButton(text="✅ Беру", callback_data=f"use:{post_id}"),
                InlineKeyboardButton(text="🗑 Не то", callback_data=f"discard:{post_id}"),
            ]
        ]
    )


async def _pick_idea(session) -> ContentIdea:
    result = await session.execute(
        select(ContentIdea).where(ContentIdea.status == IdeaStatus.NEW).order_by(ContentIdea.created_at)
    )
    idea = result.scalars().first()
    if idea:
        return idea

    recent = await session.execute(
        select(ContentIdea.title).order_by(ContentIdea.created_at.desc()).limit(15)
    )
    recent_titles = [row[0] for row in recent.all()]
    generated = await generate_idea(recent_titles)
    idea = ContentIdea(title=generated["title"], angle=generated["angle"], source="ai")
    session.add(idea)
    await session.flush()
    return idea


async def run_draft_generation(bot: Bot) -> None:
    async with get_session() as session:
        idea = await _pick_idea(session)
        draft_text = await generate_draft(idea.title, idea.angle or "")

        post = Post(idea_title=idea.title, idea_angle=idea.angle, content=draft_text)
        session.add(post)
        idea.status = IdeaStatus.USED
        await session.commit()
        await session.refresh(post)

        message = await bot.send_message(
            settings.admin_chat_id,
            f"📝 Черновик поста\n\n{draft_text}\n\n— идея: {idea.title}",
            reply_markup=draft_keyboard(post.id),
        )
        post.telegram_message_id = message.message_id
        await session.commit()


async def run_daily_post(bot: Bot) -> None:
    await run_draft_generation(bot)

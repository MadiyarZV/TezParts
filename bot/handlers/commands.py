from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select

from bot.db.models import ContentIdea, IdeaStatus, Post
from bot.db.session import get_session
from bot.jobs.daily_post import run_draft_generation

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я готовлю черновики постов для Threads.\n\n"
        "Команды:\n"
        "/draft — сгенерировать черновик прямо сейчас\n"
        "/ideas — показать бэклог идей\n"
        "/idea <текст> — добавить свою идею в бэклог\n"
        "/history — последние черновики\n\n"
        "Публикация пока ручная: беру черновик и сам постю в Threads."
    )


@router.message(Command("draft"))
async def cmd_draft(message: Message) -> None:
    await message.answer("Генерирую черновик...")
    await run_draft_generation(message.bot)


@router.message(Command("ideas"))
async def cmd_ideas(message: Message) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(ContentIdea)
            .where(ContentIdea.status == IdeaStatus.NEW)
            .order_by(ContentIdea.created_at)
            .limit(20)
        )
        ideas = result.scalars().all()

    if not ideas:
        await message.answer("Бэклог идей пуст.")
        return

    lines = [f"{i + 1}. {idea.title}" for i, idea in enumerate(ideas)]
    await message.answer("Бэклог идей:\n" + "\n".join(lines))


@router.message(Command("idea"))
async def cmd_add_idea(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Использование: /idea <текст идеи>")
        return

    async with get_session() as session:
        session.add(ContentIdea(title=command.args.strip(), source="manual"))
        await session.commit()
    await message.answer("Добавил идею в бэклог.")


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    async with get_session() as session:
        result = await session.execute(select(Post).order_by(Post.created_at.desc()).limit(5))
        posts = result.scalars().all()

    if not posts:
        await message.answer("Черновиков пока нет.")
        return

    lines = [f"[{p.status.value}] {p.idea_title} — {p.created_at:%d.%m %H:%M}" for p in posts]
    await message.answer("Последние черновики:\n" + "\n".join(lines))

from bot.ai.client import brand_voice_prompt, complete


async def generate_idea(recent_titles: list[str]) -> dict[str, str]:
    avoid = "\n".join(f"- {t}" for t in recent_titles) or "(пока пусто)"
    system = brand_voice_prompt()
    user = (
        "Предложи ОДНУ свежую идею для поста. Не повторяй темы из списка недавних:\n"
        f"{avoid}\n\n"
        "Ответь строго в этом формате, без ничего лишнего:\n"
        "ЗАГОЛОВОК: <короткая суть идеи одной строкой>\n"
        "УГОЛ: <в 1-2 предложениях, какой ракурс/зацепка у поста>"
    )
    raw = await complete(system, user, max_tokens=300)
    title, angle = "", ""
    for line in raw.splitlines():
        if line.upper().startswith("ЗАГОЛОВОК:"):
            title = line.split(":", 1)[1].strip()
        elif line.upper().startswith("УГОЛ:"):
            angle = line.split(":", 1)[1].strip()
    return {"title": title or raw.strip()[:120], "angle": angle}


async def generate_draft(idea_title: str, idea_angle: str) -> str:
    system = brand_voice_prompt()
    user = (
        f"Напиши черновик поста по идее.\n"
        f"Идея: {idea_title}\n"
        f"Угол: {idea_angle}\n\n"
        "Выведи ТОЛЬКО текст поста, без заголовков, без кавычек, без пояснений."
    )
    return await complete(system, user, max_tokens=400)


async def regenerate_draft(idea_title: str, idea_angle: str, previous_draft: str) -> str:
    system = brand_voice_prompt()
    user = (
        f"Идея: {idea_title}\n"
        f"Угол: {idea_angle}\n\n"
        f"Предыдущий вариант не подошёл:\n{previous_draft}\n\n"
        "Напиши ДРУГОЙ вариант поста по той же идее — другой хук, другая подача. "
        "Выведи ТОЛЬКО текст поста, без заголовков, без кавычек, без пояснений."
    )
    return await complete(system, user, max_tokens=400)

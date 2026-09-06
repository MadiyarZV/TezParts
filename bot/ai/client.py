from anthropic import AsyncAnthropic

from bot.config import settings

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def brand_voice_prompt() -> str:
    return (
        f"Бизнес: {settings.business_name}. Ниша: {settings.niche_description}.\n"
        f"Голос бренда: {settings.brand_voice_notes}\n"
        "Жёсткие правила для постов (формат Threads, даже если сейчас публикуем вручную):\n"
        "- Максимум 500 символов на пост.\n"
        "- Не больше одного хэштега, и то не всегда нужен.\n"
        "- Хук в первой строке, должен зацепить за 1-2 секунды.\n"
        "- Никаких длинных тире, канцелярита и AI-штампов "
        "(leverage, delve, elevate, 'в мире современных технологий' и т.п.).\n"
        "- Пиши как живой человек, разговорно, короткими фразами.\n"
        "- Никаких списков из ровно трёх пунктов подряд — это выдаёт нейросеть.\n"
    )


async def complete(system: str, user: str, max_tokens: int = 800) -> str:
    response = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()

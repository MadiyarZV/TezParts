"""Тонкая обёртка над Claude Agent SDK.

Единственное место в проекте, которое знает о форме SDK. Всё остальное
работает со строками, поэтому смена версии SDK чинится правкой одного файла.

Скиллы (threads-post-writer, humanizer-ru и т.д.) агент подхватывает из
`<workspace>/.claude/skills` — туда их надо положить (см. README).
"""
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — контент-редактор аккаунта @tez.parts (автозапчасти, Казахстан).

Работаешь через установленные скиллы. Для поста в Threads всегда прогоняй
цепочку: threads-post-writer -> humanizer-ru. Никогда не отдавай текст,
не прошедший humanizer-ru.

Отдавай ТОЛЬКО готовый текст поста. Без преамбул, без пояснений, без
markdown-разметки, без вариантов на выбор — один финальный текст.
"""


def _extract_text(message: object) -> str:
    """Достаёт текст из сообщения SDK, не завися от точных имён классов."""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


class ContentAgent:
    def __init__(self, workspace: Path, model: str):
        self.workspace = workspace
        self.model = model

    async def run(self, prompt: str) -> str:
        from claude_agent_sdk import ClaudeAgentOptions, query

        options = ClaudeAgentOptions(
            model=self.model,
            cwd=str(self.workspace),
            system_prompt=SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            setting_sources=["project"],
        )

        chunks: list[str] = []
        async for message in query(prompt=prompt, options=options):
            text = _extract_text(message)
            if text:
                chunks.append(text)

        result = "\n".join(c.strip() for c in chunks if c.strip()).strip()
        if not result:
            raise RuntimeError("агент не вернул текста")
        return result

    async def write_post(self, topic: str) -> str:
        return await self.run(
            f"Напиши один пост для Threads на тему: {topic}\n\n"
            "Используй скилл threads-post-writer, затем humanizer-ru."
        )

    async def rewrite_post(self, previous: str, feedback: str) -> str:
        return await self.run(
            "Перепиши пост для Threads с учётом правки.\n\n"
            f"Текущий текст:\n{previous}\n\n"
            f"Правка: {feedback}\n\n"
            "Прогони результат через humanizer-ru."
        )

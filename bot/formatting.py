"""Markdown Claude → HTML Telegram + нарезка на сообщения.

Telegram не понимает markdown Claude: MarkdownV2 требует экранировать
полтора десятка символов и падает на любой несбалансированной звёздочке.
HTML-режим устойчивее, поэтому конвертируем сами и поддерживаем ровно тот
набор тегов, который Telegram принимает.
"""
from __future__ import annotations

import html
import re

TELEGRAM_LIMIT = 4096
CHUNK_LIMIT = 3800  # запас на теги, которые добавит конвертер

_FENCE = re.compile(r"^\s*```")


def split_markdown(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Режет markdown на куски по границам строк, не разрывая блоки кода."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    in_fence = False
    fence_header = "```"

    def flush(carry_fence: bool) -> None:
        nonlocal current, size
        if not current:
            return
        block = "\n".join(current)
        if carry_fence:
            block += "\n```"
        chunks.append(block)
        current = ["```"] if carry_fence else []
        size = len(current[0]) if current else 0

    for line in text.split("\n"):
        # Очень длинную строку без переносов режем принудительно.
        while len(line) > limit:
            flush(in_fence)
            chunks.append(line[:limit])
            line = line[limit:]

        if size + len(line) + 1 > limit and current:
            flush(in_fence)
            if in_fence:
                current = [fence_header]
                size = len(fence_header)

        if _FENCE.match(line):
            if not in_fence:
                fence_header = line.strip()
            in_fence = not in_fence

        current.append(line)
        size += len(line) + 1

    flush(False)
    return [chunk for chunk in chunks if chunk.strip()]


def to_telegram_html(text: str) -> str:
    """Конвертирует markdown в подмножество HTML, которое понимает Telegram."""
    stash: list[str] = []

    def stash_block(match: re.Match) -> str:
        lang, body = match.group(1), match.group(2)
        code = html.escape(body.rstrip("\n"))
        cls = f' class="language-{html.escape(lang)}"' if lang else ""
        stash.append(f"<pre><code{cls}>{code}</code></pre>")
        return f"\x00{len(stash) - 1}\x00"

    def stash_inline(match: re.Match) -> str:
        stash.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(stash) - 1}\x00"

    text = re.sub(r"```(\w*)\n(.*?)```", stash_block, text, flags=re.DOTALL)
    text = re.sub(r"`([^`\n]+)`", stash_inline, text)

    text = html.escape(text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "• ", text, flags=re.MULTILINE)

    for index, block in enumerate(stash):
        text = text.replace(f"\x00{index}\x00", block)
    return text


def render(text: str) -> list[str]:
    """Готовые к отправке HTML-куски."""
    return [to_telegram_html(chunk) for chunk in split_markdown(text)]

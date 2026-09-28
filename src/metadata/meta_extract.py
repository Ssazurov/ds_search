"""issue #92: author/publish_date/description из og:*/meta-тегов, без LLM.

Использует result.metadata, который crawl4ai уже собирает из HTML (og:*,
article:*, name=description/author) — здесь только приоритет и нормализация
под sidecar-схему (issue #33).
"""
from __future__ import annotations

import re

_AUTHOR_LINE_RE = re.compile(r"^\s*Авторы?:\s*(.+)$", re.MULTILINE)


def extract_author_from_markdown(markdown: str) -> str:
    """Извлечь автора вместе с markdown-ссылкой из строки ``Автор:``."""
    m = _AUTHOR_LINE_RE.search(markdown or "")
    if not m:
        return ""
    line = m.group(1).split("Журнал:")[0]
    return line.strip(" ,;")


def extract_page_meta(metadata: dict | None, markdown: str = "") -> dict:
    """Вернуть {author, publish_date, description} (пустая строка, если нет)."""
    metadata = metadata or {}

    description = (
        metadata.get('og:description')
        or metadata.get('description')
        or metadata.get('twitter:description')
        or ''
    ).strip()

    author = (
        metadata.get('article:author')
        or metadata.get('author')
        or metadata.get('twitter:creator')
        or ''
    ).strip()

    # issue #338: article:author у части сайтов — ссылка на соцсеть издания
    # (facebook.com/foma.ru), не автор. Реальный автор — из тела статьи.
    body_author = extract_author_from_markdown(markdown)
    if body_author:
        author = body_author
    elif author.lower().startswith(("http://", "https://")):
        author = ""

    publish_date = (
        metadata.get('article:published_time')
        or metadata.get('og:published_time')
        or metadata.get('article:modified_time')
        or ''
    ).strip()

    return {'author': author, 'publish_date': publish_date, 'description': description}

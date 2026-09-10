"""issue #92: author/publish_date/description из og:*/meta-тегов, без LLM.

Использует result.metadata, который crawl4ai уже собирает из HTML (og:*,
article:*, name=description/author) — здесь только приоритет и нормализация
под sidecar-схему (issue #33).
"""
from __future__ import annotations


def extract_page_meta(metadata: dict | None) -> dict:
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

    publish_date = (
        metadata.get('article:published_time')
        or metadata.get('og:published_time')
        or metadata.get('article:modified_time')
        or ''
    ).strip()

    return {'author': author, 'publish_date': publish_date, 'description': description}

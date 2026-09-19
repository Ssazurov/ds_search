"""Ручное создание черновика новости (issue #217). Без LLM и проверки лицензии."""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from src.news import db

DEFAULT_SOURCE_NAME = "Редакция"
MANUAL_URL_PREFIX = "manual:"
SUMMARY_LEN = 300


def create_manual_draft(
    title: str,
    body_md: str,
    summary: str = "",
    source_name: str = DEFAULT_SOURCE_NAME,
    source_url: str = "",
    source_published_at: str = "",
    tags: list[str] | None = None,
    requires_review: bool = True,
    db_path: Path = db.DB_PATH,
) -> int:
    """Создать draft в news_items. ValueError — пустые поля/дубль URL."""
    title, body_md = title.strip(), body_md.strip()
    if not title or not body_md:
        raise ValueError("Заголовок и текст обязательны")
    source_url = source_url.strip() or f"{MANUAL_URL_PREFIX}{uuid.uuid4()}"
    item = {
        "source_url": source_url,
        "source_name": source_name.strip() or DEFAULT_SOURCE_NAME,
        "source_published_at": source_published_at.strip() or None,
        "title": title,
        "summary": summary.strip() or body_md[:SUMMARY_LEN],
        "body_md": body_md,
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "requires_review": requires_review,
        "status": "draft",
    }
    try:
        return db.insert_news_item(item, db_path=db_path)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Новость с такой ссылкой уже есть") from exc

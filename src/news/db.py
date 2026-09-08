"""SQLite-хранилище news_items (issue #45, ADR-003).

Своя БД (не GAR Postgres) — во избежание конфликта alembic-цепочки GAR.
Миграция — простой CREATE TABLE IF NOT EXISTS, без Alembic (объём схемы
не оправдывает инструмент).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "news.db"

STATUSES = ("draft", "published", "rejected")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL UNIQUE,
    source_name TEXT,
    source_published_at TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    body_md TEXT,
    direction TEXT NOT NULL DEFAULT 'news',
    tags TEXT NOT NULL DEFAULT '[]',
    requires_review INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'rejected')),
    channels TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    published_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_items_status ON news_items(status);
"""

# issue #49: идемпотентность publish-адаптера (GAR ingestion) + диагностика
# последней ошибки публикации. ALTER TABLE — т.к. CREATE TABLE IF NOT EXISTS
# не добавляет колонки в уже существующую БД (data/news.db).
_MIGRATIONS = (
    "ALTER TABLE news_items ADD COLUMN gar_document_id TEXT",
    "ALTER TABLE news_items ADD COLUMN publish_error TEXT",
)


@contextmanager
def get_connection(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Идемпотентная миграция: создать таблицу news_items, если её нет."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # колонка уже существует
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    d["channels"] = json.loads(d["channels"])
    d["requires_review"] = bool(d["requires_review"])
    return d


def insert_news_item(item: dict, db_path: Path = DB_PATH) -> int:
    """Вставить черновик новости. item — dict с полями схемы (см. модуль).
    tags/channels — списки (сериализуются в JSON). Возвращает id.
    Дубликат source_url -> sqlite3.IntegrityError (дедуп по UNIQUE, issue #47).
    """
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO news_items
                (source_url, source_name, source_published_at, title,
                 summary, body_md, direction, tags, requires_review,
                 status, channels)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["source_url"],
                item.get("source_name"),
                item.get("source_published_at"),
                item["title"],
                item.get("summary"),
                item.get("body_md"),
                item.get("direction", "news"),
                json.dumps(item.get("tags", []), ensure_ascii=False),
                int(item.get("requires_review", False)),
                item.get("status", "draft"),
                json.dumps(item.get("channels", []), ensure_ascii=False),
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_news_item(item_id: int, db_path: Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM news_items WHERE id = ?", (item_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None


def list_news_items(status: str | None = None, db_path: Path = DB_PATH) -> list[dict]:
    query = "SELECT * FROM news_items"
    params: tuple = ()
    if status is not None:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY created_at DESC"
    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def update_status(item_id: int, status: str, db_path: Path = DB_PATH) -> None:
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    published_at_clause = ", published_at = datetime('now')" if status == "published" else ""
    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE news_items SET status = ?{published_at_clause} WHERE id = ?",
            (status, item_id),
        )
        conn.commit()


EDITABLE_FIELDS = ("title", "summary", "body_md", "tags", "channels")


def update_news_item(item_id: int, fields: dict, db_path: Path = DB_PATH) -> None:
    """Частичное обновление редактируемых полей (issue #48, ревью в UI).
    tags/channels — списки, сериализуются в JSON. Неизвестные ключи в
    fields игнорируются.
    """
    cols, params = [], []
    for key in EDITABLE_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key in ("tags", "channels"):
            value = json.dumps(value, ensure_ascii=False)
        cols.append(f"{key} = ?")
        params.append(value)
    if not cols:
        return
    params.append(item_id)
    with get_connection(db_path) as conn:
        conn.execute(f"UPDATE news_items SET {', '.join(cols)} WHERE id = ?", params)
        conn.commit()


def delete_news_item(item_id: int, db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM news_items WHERE id = ?", (item_id,))
        conn.commit()


def set_publish_result(
    item_id: int, gar_document_id: str | None, error: str | None, db_path: Path = DB_PATH,
) -> None:
    """Итог попытки publish-адаптера (issue #49): document_id при успехе,
    error при неудаче (успех всегда чистит error, ошибка не трогает
    предыдущий document_id, если он уже был)."""
    with get_connection(db_path) as conn:
        if gar_document_id is not None:
            conn.execute(
                "UPDATE news_items SET gar_document_id = ?, publish_error = NULL WHERE id = ?",
                (gar_document_id, item_id),
            )
        else:
            conn.execute(
                "UPDATE news_items SET publish_error = ? WHERE id = ?", (error, item_id),
            )
        conn.commit()

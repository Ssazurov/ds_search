"""Тесты src/news/db.py (issue #45)."""
import sqlite3
from pathlib import Path

import pytest

from src.news.db import (
    init_db,
    insert_news_item,
    get_news_item,
    list_news_items,
    update_status,
    update_news_item,
    delete_news_item,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "news_test.db"
    init_db(p)
    return p


def _item(**overrides) -> dict:
    base = {
        "source_url": "https://example.com/a",
        "source_name": "Example",
        "title": "Заголовок",
    }
    base.update(overrides)
    return base


def test_init_db_idempotent(db_path):
    init_db(db_path)  # повторный вызов не должен падать
    assert db_path.exists()


def test_insert_and_get(db_path):
    item_id = insert_news_item(_item(tags=["a", "b"], channels=["telegram"]), db_path)
    item = get_news_item(item_id, db_path)
    assert item["source_url"] == "https://example.com/a"
    assert item["tags"] == ["a", "b"]
    assert item["channels"] == ["telegram"]
    assert item["direction"] == "news"
    assert item["status"] == "draft"
    assert item["requires_review"] is False


def test_duplicate_source_url_raises(db_path):
    insert_news_item(_item(), db_path)
    with pytest.raises(sqlite3.IntegrityError):
        insert_news_item(_item(), db_path)


def test_list_news_items_filters_by_status(db_path):
    id1 = insert_news_item(_item(source_url="https://example.com/1"), db_path)
    insert_news_item(_item(source_url="https://example.com/2"), db_path)
    update_status(id1, "published", db_path)

    published = list_news_items(status="published", db_path=db_path)
    drafts = list_news_items(status="draft", db_path=db_path)
    assert [i["id"] for i in published] == [id1]
    assert len(drafts) == 1


def test_update_status_sets_published_at(db_path):
    item_id = insert_news_item(_item(), db_path)
    update_status(item_id, "published", db_path)
    item = get_news_item(item_id, db_path)
    assert item["status"] == "published"
    assert item["published_at"] is not None


def test_update_status_invalid_raises(db_path):
    item_id = insert_news_item(_item(), db_path)
    with pytest.raises(ValueError):
        update_status(item_id, "bogus", db_path)


def test_get_news_item_missing_returns_none(db_path):
    assert get_news_item(999, db_path) is None


def test_update_news_item_edits_fields(db_path):
    item_id = insert_news_item(_item(tags=["a"], channels=[]), db_path)
    update_news_item(item_id, {
        "title": "Новый заголовок", "summary": "Кратко", "body_md": "Текст",
        "tags": ["x", "y"], "channels": ["telegram"],
    }, db_path)
    item = get_news_item(item_id, db_path)
    assert item["title"] == "Новый заголовок"
    assert item["summary"] == "Кратко"
    assert item["body_md"] == "Текст"
    assert item["tags"] == ["x", "y"]
    assert item["channels"] == ["telegram"]


def test_update_news_item_ignores_unknown_fields(db_path):
    item_id = insert_news_item(_item(), db_path)
    update_news_item(item_id, {"status": "published", "id": 999}, db_path)
    item = get_news_item(item_id, db_path)
    assert item["status"] == "draft"  # неизвестные/неразрешённые поля не тронуты


def test_update_news_item_noop_on_empty_fields(db_path):
    item_id = insert_news_item(_item(), db_path)
    update_news_item(item_id, {}, db_path)  # не должно падать
    assert get_news_item(item_id, db_path)["title"] == "Заголовок"


def test_delete_news_item(db_path):
    item_id = insert_news_item(_item(), db_path)
    delete_news_item(item_id, db_path)
    assert get_news_item(item_id, db_path) is None

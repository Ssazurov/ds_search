"""Тесты src/news/publish.py (issue #49)."""
from pathlib import Path

import pytest

from src.news import db, publish


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "news_test.db"
    db.init_db(p)
    return p


def _item(**overrides) -> dict:
    base = {
        "source_url": "https://example.com/news/1",
        "source_name": "Example",
        "title": "Новость про СД",
        "summary": "Кратко о новости",
        "body_md": "Полный **текст** новости.",
        "tags": ["сд", "новости"],
    }
    base.update(overrides)
    return base


def test_build_content_md_uses_body():
    item = _item()
    content = publish.build_content_md(item)
    assert content.startswith("# Новость про СД")
    assert "Полный **текст** новости." in content


def test_build_content_md_falls_back_to_summary():
    item = _item(body_md=None)
    content = publish.build_content_md(item)
    assert "Кратко о новости" in content


def test_build_metadata_mapping():
    item = _item(published_at="2026-09-08 10:00:00")
    meta = publish.build_metadata(item)
    assert meta["doc_type"] == "news"
    assert meta["license"] == "own_generated"
    assert meta["direction"] == "news"
    assert meta["source_domain"] == "example.com"
    assert meta["keywords"] == "сд, новости"
    assert meta["publish_date"] == "2026-09-08 10:00:00"
    assert meta["category"] == "basic"
    assert meta["lifecycle_stage"] == "unspecified"
    assert meta["date_indexed"]


def test_build_metadata_omits_empty_fields():
    item = _item(tags=[], summary=None)
    meta = publish.build_metadata(item)
    assert "keywords" not in meta
    assert "description" not in meta


class _FakeClient:
    def __init__(self):
        self.ingested = []

    def ensure_dataset(self, name):
        return "dataset-1"

    def ingest_document(self, dataset_id, file_path, doc_name, metadata):
        assert file_path.exists()
        self.ingested.append((dataset_id, doc_name, metadata))
        return {"document_id": "doc-42"}


def test_publish_news_item_happy_path(db_path):
    item_id = db.insert_news_item(_item(), db_path)
    db.update_status(item_id, "published", db_path)
    client = _FakeClient()
    settings = publish.load_settings()

    result = publish.publish_news_item(item_id, settings=settings, db_path=db_path, client=client)

    assert result == {"skipped": False, "item_id": item_id, "gar_document_id": "doc-42"}
    assert len(client.ingested) == 1
    item = db.get_news_item(item_id, db_path)
    assert item["gar_document_id"] == "doc-42"
    assert item["publish_error"] is None


def test_publish_news_item_requires_published_status(db_path):
    item_id = db.insert_news_item(_item(), db_path)  # остаётся draft
    with pytest.raises(ValueError):
        publish.publish_news_item(item_id, db_path=db_path, client=_FakeClient())


def test_publish_news_item_missing_raises(db_path):
    with pytest.raises(ValueError):
        publish.publish_news_item(999, db_path=db_path, client=_FakeClient())


def test_publish_news_item_idempotent_skips(db_path):
    item_id = db.insert_news_item(_item(), db_path)
    db.update_status(item_id, "published", db_path)
    client = _FakeClient()
    publish.publish_news_item(item_id, db_path=db_path, client=client)

    result = publish.publish_news_item(item_id, db_path=db_path, client=client)

    assert result["skipped"] is True
    assert len(client.ingested) == 1  # второй раз не дергали ingest


def test_publish_news_item_force_reingests(db_path):
    item_id = db.insert_news_item(_item(), db_path)
    db.update_status(item_id, "published", db_path)
    client = _FakeClient()
    publish.publish_news_item(item_id, db_path=db_path, client=client)

    result = publish.publish_news_item(item_id, db_path=db_path, client=client, force=True)

    assert result["skipped"] is False
    assert len(client.ingested) == 2


class _FailingClient(_FakeClient):
    def ingest_document(self, dataset_id, file_path, doc_name, metadata):
        raise publish.GarPublishError("boom")


def test_publish_news_item_records_error(db_path):
    item_id = db.insert_news_item(_item(), db_path)
    db.update_status(item_id, "published", db_path)

    with pytest.raises(publish.GarPublishError):
        publish.publish_news_item(item_id, db_path=db_path, client=_FailingClient())

    item = db.get_news_item(item_id, db_path)
    assert item["publish_error"] == "boom"
    assert item["gar_document_id"] is None

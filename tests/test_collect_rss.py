"""Тесты src/news/collect.py:collect_rss (issue #157/#159, ADR-010)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.news import collect, db
from src.news.rss import RssHit


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "news_test.db"
    db.init_db(p)
    return p


def _draft_item(source: dict) -> dict:
    return {
        "source_url": source["source_url"],
        "source_name": source.get("source_name"),
        "source_published_at": source.get("source_published_at"),
        "title": "Черновик: " + source["title"],
        "summary": "summary",
        "body_md": "body",
        "direction": "news",
        "tags": ["сд"],
        "requires_review": True,
        "status": "draft",
        "channels": [],
    }


async def _fake_download_ok(source: dict, data_root=None, _tmp_path=None) -> dict:
    md_path = _tmp_path / f"{source['domain']}.md"
    md_path.write_text("Текст источника.", encoding="utf-8")
    return {
        "source_url": source["url"],
        "source_domain": source["domain"],
        "title": source["title"],
        "content_path": str(md_path),
        "content_status": "saved",
    }


def test_collect_rss_happy_path_passes_published_at(db_path, tmp_path, monkeypatch):
    published = datetime(2026, 9, 1, tzinfo=timezone.utc)
    hit = RssHit(url="https://a.org/1", title="Новость", source_name="a.org", published_at=published)
    monkeypatch.setattr("src.news.rss.fetch_all", lambda *a, **kw: [hit])

    captured = {}

    async def fake_download(source, data_root=None):
        return await _fake_download_ok(source, data_root, tmp_path)

    def fake_draft(source, config=None):
        captured["source_published_at"] = source["source_published_at"]
        return _draft_item(source)

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", fake_draft)

    stats = asyncio.run(collect.collect_rss(db_path=db_path))

    assert stats.drafted == 1
    assert captured["source_published_at"] == "2026-09-01T00:00:00+00:00"


def test_collect_rss_skips_existing_by_dedup(db_path, tmp_path, monkeypatch):
    db.insert_news_item(_draft_item({"source_url": "https://a.org/1", "title": "x"}), db_path)
    hit = RssHit(url="https://a.org/1", title="Новость", source_name="a.org", published_at=None)
    monkeypatch.setattr("src.news.rss.fetch_all", lambda *a, **kw: [hit])

    called = {"n": 0}

    async def fake_download(source, data_root=None):
        called["n"] += 1
        return await _fake_download_ok(source, data_root, tmp_path)

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", lambda source, config=None: _draft_item(source))

    stats = asyncio.run(collect.collect_rss(db_path=db_path))

    assert stats.skipped_duplicate == 1
    assert stats.drafted == 0
    assert called["n"] == 0

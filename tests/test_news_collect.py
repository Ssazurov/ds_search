"""Тесты src/news/collect.py — cron-пайплайн автосбора новостей (issue #61)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.discovery.download import DownloadError
from src.news import collect, db
from src.search.base import QuotaExceeded, SearchHit


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "news_test.db"
    db.init_db(p)
    return p


class _FakeChain:
    """Дублирует интерфейс SearchProviderChain.search(query, max_results)."""

    def __init__(self, hits_by_query: dict[str, list[SearchHit]] | None = None, raise_for: set[str] | None = None):
        self.hits_by_query = hits_by_query or {}
        self.raise_for = raise_for or set()
        self.calls: list[str] = []

    def search(self, query: str, max_results: int = 10) -> list[SearchHit]:
        self.calls.append(query)
        if query in self.raise_for:
            raise QuotaExceeded(f"quota for {query}")
        return self.hits_by_query.get(query, [])


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
    md_path.write_text("Полный текст источника про синдром Дауна.", encoding="utf-8")
    return {
        "source_url": source["url"],
        "source_domain": source["domain"],
        "title": source["title"],
        "content_path": str(md_path),
        "content_status": "saved",
    }


def test_collect_news_happy_path(db_path, tmp_path, monkeypatch):
    hit = SearchHit(url="https://a.org/news/1", title="Новость 1", snippet="s")
    chain = _FakeChain({"сд новости": [hit]})

    async def fake_download(source, data_root=None):
        return await _fake_download_ok(source, data_root, tmp_path)

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", lambda source, config=None: _draft_item(source))

    stats = asyncio.run(collect.collect_news(
        chain, queries=[{"query": "сд новости"}], max_results=5, db_path=db_path,
    ))

    assert stats.drafted == 1
    assert stats.candidates_found == 1
    items = db.list_news_items(db_path=db_path)
    assert len(items) == 1
    assert items[0]["source_url"] == "https://a.org/news/1"


def test_collect_news_skips_existing_by_dedup(db_path, tmp_path, monkeypatch):
    db.insert_news_item(_draft_item({"source_url": "https://a.org/news/1", "title": "x"}), db_path)
    hit = SearchHit(url="https://a.org/news/1", title="Новость 1", snippet="s")
    chain = _FakeChain({"q": [hit]})

    called = {"n": 0}

    async def fake_download(source, data_root=None):
        called["n"] += 1
        return await _fake_download_ok(source, data_root, tmp_path)

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", lambda source, config=None: _draft_item(source))

    stats = asyncio.run(collect.collect_news(chain, queries=[{"query": "q"}], max_results=5, db_path=db_path))

    assert stats.skipped_duplicate == 1
    assert stats.drafted == 0
    assert called["n"] == 0  # download не вызывался — дедуп сработал раньше


def test_collect_news_license_denied_is_skipped(db_path, monkeypatch):
    hit = SearchHit(url="https://b.org/news/1", title="Новость", snippet="s")
    chain = _FakeChain({"q": [hit]})

    async def fake_download(source, data_root=None):
        raise DownloadError("license status pending_manual_review: домен b.org отсутствует в реестре")

    monkeypatch.setattr(collect, "download_single", fake_download)

    stats = asyncio.run(collect.collect_news(chain, queries=[{"query": "q"}], max_results=5, db_path=db_path))

    assert stats.skipped_license == 1
    assert stats.drafted == 0
    assert db.list_news_items(db_path=db_path) == []


def test_collect_news_download_error_does_not_stop_run(db_path, tmp_path, monkeypatch):
    bad = SearchHit(url="https://c.org/1", title="bad", snippet="s")
    good = SearchHit(url="https://c.org/2", title="good", snippet="s")
    chain = _FakeChain({"q": [bad, good]})

    async def fake_download(source, data_root=None):
        if source["url"].endswith("/1"):
            raise DownloadError("fetch failed: timeout")
        return await _fake_download_ok(source, data_root, tmp_path)

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", lambda source, config=None: _draft_item(source))

    stats = asyncio.run(collect.collect_news(chain, queries=[{"query": "q"}], max_results=5, db_path=db_path))

    assert stats.download_failed == 1
    assert stats.drafted == 1


def test_collect_news_llm_failure_does_not_stop_run(db_path, tmp_path, monkeypatch):
    hit = SearchHit(url="https://d.org/1", title="Новость", snippet="s")
    chain = _FakeChain({"q": [hit]})

    async def fake_download(source, data_root=None):
        return await _fake_download_ok(source, data_root, tmp_path)

    def failing_draft(source, config=None):
        raise RuntimeError("LLM недоступен")

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", failing_draft)

    stats = asyncio.run(collect.collect_news(chain, queries=[{"query": "q"}], max_results=5, db_path=db_path))

    assert stats.llm_failed == 1
    assert stats.drafted == 0


def test_collect_news_query_quota_exceeded_does_not_stop_other_queries(db_path, tmp_path, monkeypatch):
    hit = SearchHit(url="https://e.org/1", title="Новость", snippet="s")
    chain = _FakeChain({"q2": [hit]}, raise_for={"q1"})

    async def fake_download(source, data_root=None):
        return await _fake_download_ok(source, data_root, tmp_path)

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", lambda source, config=None: _draft_item(source))

    stats = asyncio.run(collect.collect_news(
        chain, queries=[{"query": "q1"}, {"query": "q2"}], max_results=5, db_path=db_path,
    ))

    assert stats.queries_failed == 1
    assert stats.queries_run == 1
    assert stats.drafted == 1


def test_load_queries_config_reads_yaml(tmp_path):
    cfg = tmp_path / "queries.yaml"
    cfg.write_text(
        "max_results_per_query: 3\nqueries:\n  - query: \"тест\"\n", encoding="utf-8",
    )
    queries, max_results = collect.load_queries_config(cfg)
    assert max_results == 3
    assert queries == [{"query": "тест"}]

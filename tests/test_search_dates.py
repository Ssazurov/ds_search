"""Тесты parse_published и published_at у провайдеров (ds_search #355)."""
from datetime import datetime, timezone

import httpx
import pytest

from src.search import BraveProvider, TavilyProvider
from src.search.dates import parse_published

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("raw,expected", [
    ("2026-09-01", datetime(2026, 9, 1, tzinfo=timezone.utc)),
    ("2026-09-01T10:00:00Z", datetime(2026, 9, 1, 10, tzinfo=timezone.utc)),
    ("2026-09-01T10:00:00+03:00", datetime(2026, 9, 1, 7, tzinfo=timezone.utc)),
    ("Tue, 01 Sep 2026 10:00:00 GMT", datetime(2026, 9, 1, 10, tzinfo=timezone.utc)),
    ("3 days ago", datetime(2026, 9, 26, 12, tzinfo=timezone.utc)),
    ("2 weeks ago", datetime(2026, 9, 15, 12, tzinfo=timezone.utc)),
    ("1 month ago", datetime(2026, 8, 30, 12, tzinfo=timezone.utc)),
    ("5 hours ago", datetime(2026, 9, 29, 7, tzinfo=timezone.utc)),
])
def test_parse_published_formats(raw, expected):
    assert parse_published(raw, now=NOW) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "вчера", "not a date", 123])
def test_parse_published_garbage_returns_none(raw):
    assert parse_published(raw, now=NOW) is None


def test_brave_fills_published_at(tmp_path, monkeypatch):
    provider = BraveProvider(api_key="fake", quota_path=tmp_path / "q.json")
    body = {"web": {"results": [
        {"url": "https://x.org/a", "title": "A", "description": "a", "page_age": "2026-08-15T09:00:00"},
        {"url": "https://x.org/b", "title": "B", "description": "b", "age": "3 days ago"},
        {"url": "https://x.org/c", "title": "C", "description": "c"},
    ]}}
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: httpx.Response(
        200, json=body, request=httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search")))
    hits = provider.search("q")
    assert hits[0].published_at == datetime(2026, 8, 15, 9, tzinfo=timezone.utc)
    assert hits[1].published_at is not None
    assert hits[2].published_at is None


def test_tavily_fills_published_at(tmp_path, monkeypatch):
    provider = TavilyProvider(api_key="fake", quota_path=tmp_path / "q.json")
    body = {"results": [
        {"url": "https://x.org/a", "title": "A", "content": "a", "published_date": "Tue, 01 Sep 2026 10:00:00 GMT"},
        {"url": "https://x.org/b", "title": "B", "content": "b"},
    ]}
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(
        200, json=body, request=httpx.Request("POST", "https://api.tavily.com/search")))
    hits = provider.search("q")
    assert hits[0].published_at == datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    assert hits[1].published_at is None


def test_firecrawl_published_from_metadata(tmp_path, monkeypatch):
    from src.search.firecrawl import FirecrawlProvider
    provider = FirecrawlProvider(api_key="fake", quota_path=tmp_path / "q.json")
    body = {"data": [
        {"url": "https://x.org/a", "title": "A", "description": "a", "metadata": {"publishedTime": "2026-09-01T10:00:00Z"}},
        {"url": "https://x.org/b", "title": "B", "description": "b"},
    ]}
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(
        200, json=body, request=httpx.Request("POST", "https://api.firecrawl.dev/v1/search")))
    hits = provider.search("q")
    assert hits[0].published_at == datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    assert hits[1].published_at is None

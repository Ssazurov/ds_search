"""Тесты src/news/rss.py — RSS-адаптер (issue #157/#158, ADR-010)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.news import rss


class _FakeEntry(dict):
    """feedparser-запись доступна и по атрибуту, и по .get() — эмулируем
    FeedParserDict минимально нужным поведением."""

    def __getattr__(self, item):
        return self.get(item)


class _FakeParsed:
    def __init__(self, entries, bozo=False, bozo_exception=None):
        self.entries = entries
        self.bozo = bozo
        self._bozo_exception = bozo_exception

    def get(self, key, default=None):
        if key == "bozo_exception":
            return self._bozo_exception
        return default


def _struct(dt: datetime):
    return dt.utctimetuple()


def test_fetch_feed_filters_by_freshness(monkeypatch):
    now = datetime.now(timezone.utc)
    fresh = _FakeEntry(link="https://a.org/1", title="Свежая", published_parsed=_struct(now - timedelta(days=1)))
    stale = _FakeEntry(link="https://a.org/2", title="Старая", published_parsed=_struct(now - timedelta(days=10)))
    parsed = _FakeParsed([fresh, stale])
    monkeypatch.setattr(rss.feedparser, "parse", lambda url: parsed)

    hits = rss.fetch_feed({"name": "a", "url": "https://a.org/feed/"}, max_age_days=5)

    assert [h.url for h in hits] == ["https://a.org/1"]


def test_fetch_feed_no_filter_keeps_all(monkeypatch):
    now = datetime.now(timezone.utc)
    old = _FakeEntry(link="https://a.org/2", title="Старая", published_parsed=_struct(now - timedelta(days=400)))
    parsed = _FakeParsed([old])
    monkeypatch.setattr(rss.feedparser, "parse", lambda url: parsed)

    hits = rss.fetch_feed({"name": "a", "url": "https://a.org/feed/"}, max_age_days=None)

    assert len(hits) == 1


def test_fetch_feed_keeps_entries_without_date(monkeypatch):
    entry = _FakeEntry(link="https://a.org/3", title="Без даты")
    parsed = _FakeParsed([entry])
    monkeypatch.setattr(rss.feedparser, "parse", lambda url: parsed)

    hits = rss.fetch_feed({"name": "a", "url": "https://a.org/feed/"}, max_age_days=5)

    assert len(hits) == 1
    assert hits[0].published_at is None


def test_fetch_feed_bozo_without_entries_returns_empty(monkeypatch):
    parsed = _FakeParsed([], bozo=True, bozo_exception="not xml")
    monkeypatch.setattr(rss.feedparser, "parse", lambda url: parsed)

    hits = rss.fetch_feed({"name": "a", "url": "https://a.org/broken"}, max_age_days=5)

    assert hits == []


def test_fetch_all_skips_failing_feed(monkeypatch):
    def fake_parse(url):
        if "bad" in url:
            raise RuntimeError("network error")
        return _FakeParsed([_FakeEntry(link="https://ok.org/1", title="ok")])

    monkeypatch.setattr(rss.feedparser, "parse", fake_parse)

    sources = [{"name": "bad", "url": "https://bad.org/feed/"}, {"name": "ok", "url": "https://ok.org/feed/"}]
    hits = rss.fetch_all(sources, max_age_days=5)

    assert [h.url for h in hits] == ["https://ok.org/1"]


def test_load_sources_config_reads_yaml(tmp_path):
    cfg = tmp_path / "rss_sources.yaml"
    cfg.write_text(
        "sources:\n  - name: a\n    url: https://a.org/feed/\n", encoding="utf-8",
    )
    sources = rss.load_sources_config(cfg)
    assert sources == [{"name": "a", "url": "https://a.org/feed/"}]

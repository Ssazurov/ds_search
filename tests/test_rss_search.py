from datetime import datetime, timezone
from unittest.mock import Mock

from src.search.rss_search import rss_search


class MockResponse:
    def __init__(self, status_code, text="", content=b""):
        self.status_code = status_code
        self.text = text
        self.content = content


def test_rss_search_returns_none_when_no_feed(monkeypatch):
    """RSS недоступен -> None для фолбэка."""
    def mock_get(*args, **kwargs):
        return MockResponse(404)
    monkeypatch.setattr("src.search.rss_search.httpx.get", mock_get)
    monkeypatch.setattr("src.search.rss_search.httpx.head", lambda *a, **k: MockResponse(404))
    assert rss_search("example.org", "query") is None


def test_rss_search_finds_feed_via_link_tag(monkeypatch):
    """Автообнаружение через <link rel="alternate">."""
    html = '<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>'
    feed_xml = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
<title>Test Article</title>
<link>https://example.org/post</link>
<description>Test description</description>
<pubDate>Thu, 01 Aug 2026 12:00:00 +0000</pubDate>
</item>
</channel></rss>"""
    
    calls = []
    def mock_get(url, *args, **kwargs):
        calls.append(url)
        if "example.org" in url and "feed" not in url:
            return MockResponse(200, html)
        return MockResponse(200, feed_xml)
    
    monkeypatch.setattr("src.search.rss_search.httpx.get", mock_get)
    
    def mock_entry_get(key, default=""):
        return {"link": "https://example.org/post", "title": "Test Article", 
                "summary": "Test description"}.get(key, default)
    
    mock_entry = Mock()
    mock_entry.get = mock_entry_get
    mock_entry.link = "https://example.org/post"
    mock_entry.published_parsed = (2026, 8, 1, 12, 0, 0, 0, 0, 0)
    
    mock_parsed = Mock()
    mock_parsed.bozo = False
    mock_parsed.entries = [mock_entry]
    monkeypatch.setattr("src.search.rss_search.feedparser.parse", lambda url: mock_parsed)
    
    hits = rss_search("example.org", "test")
    assert len(hits) == 1
    assert hits[0].title == "Test Article"
    assert hits[0].published_at.year == 2026


def test_rss_search_filters_by_date_range(monkeypatch):
    """Фильтр по периоду date_from/date_to."""
    def make_entry(url, title, summary, pub):
        e = Mock()
        e.get = lambda k, d="": {"link": url, "title": title, "summary": summary}.get(k, d)
        e.link = url
        e.published_parsed = pub
        return e
    
    mock_parsed = Mock()
    mock_parsed.bozo = False
    mock_parsed.entries = [
        make_entry("https://example.org/old", "Old Article", "old content", (2026, 7, 1, 12, 0, 0, 0, 0, 0)),
        make_entry("https://example.org/new", "New Article", "new content", (2026, 8, 15, 12, 0, 0, 0, 0, 0)),
    ]
    monkeypatch.setattr("src.search.rss_search.feedparser.parse", lambda url: mock_parsed)
    monkeypatch.setattr("src.search.rss_search._discover_feed", lambda d, t: "https://example.org/feed")
    
    hits = rss_search("example.org", "article", date_from=datetime(2026, 8, 1), date_to=datetime(2026, 9, 1))
    assert len(hits) == 1
    assert "new" in hits[0].url


def test_rss_search_filters_by_query(monkeypatch):
    """Фильтр по запросу в title/description."""
    def make_entry(url, title, summary, pub):
        e = Mock()
        e.get = lambda k, d="": {"link": url, "title": title, "summary": summary}.get(k, d)
        e.link = url
        e.published_parsed = pub
        return e
    
    mock_parsed = Mock()
    mock_parsed.bozo = False
    mock_parsed.entries = [
        make_entry("https://example.org/python", "Python Guide", "Learn Python", (2026, 8, 1, 12, 0, 0, 0, 0, 0)),
        make_entry("https://example.org/java", "Java Tutorial", "Learn Java", (2026, 8, 2, 12, 0, 0, 0, 0, 0)),
    ]
    monkeypatch.setattr("src.search.rss_search.feedparser.parse", lambda url: mock_parsed)
    monkeypatch.setattr("src.search.rss_search._discover_feed", lambda d, t: "https://example.org/feed")
    
    hits = rss_search("example.org", "python")
    assert len(hits) == 1
    assert "python" in hits[0].url.lower()


def test_rss_search_returns_empty_when_no_matches(monkeypatch):
    """RSS работает, но нет совпадений -> []."""
    def make_entry(url, title, summary, pub):
        e = Mock()
        e.get = lambda k, d="": {"link": url, "title": title, "summary": summary}.get(k, d)
        e.link = url
        e.published_parsed = pub
        return e
    
    mock_parsed = Mock()
    mock_parsed.bozo = False
    mock_parsed.entries = [
        make_entry("https://example.org/post", "Article", "Content", (2026, 8, 1, 12, 0, 0, 0, 0, 0)),
    ]
    monkeypatch.setattr("src.search.rss_search.feedparser.parse", lambda url: mock_parsed)
    monkeypatch.setattr("src.search.rss_search._discover_feed", lambda d, t: "https://example.org/feed")
    
    hits = rss_search("example.org", "nonexistent")
    assert hits == []


def test_rss_search_respects_max_results(monkeypatch):
    """Лимит max_results."""
    def make_entry(i):
        e = Mock()
        e.get = lambda k, d="": {"link": f"https://example.org/post{i}", 
                                  "title": f"Article {i}", "summary": "test content"}.get(k, d)
        e.link = f"https://example.org/post{i}"
        e.published_parsed = (2026, 8, 1, 12, 0, 0, 0, 0, 0)
        return e
    
    mock_parsed = Mock()
    mock_parsed.bozo = False
    mock_parsed.entries = [make_entry(i) for i in range(20)]
    monkeypatch.setattr("src.search.rss_search.feedparser.parse", lambda url: mock_parsed)
    monkeypatch.setattr("src.search.rss_search._discover_feed", lambda d, t: "https://example.org/feed")
    
    hits = rss_search("example.org", "test", max_results=5)
    assert len(hits) == 5

from datetime import datetime

from src.search import wp_api


class R:
    def __init__(self, code, data):
        self.status_code, self._d = code, data

    def json(self):
        return self._d


def test_wp_search_parses(monkeypatch):
    data = [{"link": "https://x.ru/a", "date_gmt": "2026-08-10T06:00:00",
             "title": {"rendered": "A &amp; B"}, "excerpt": {"rendered": "<p>hi</p>"}}]
    monkeypatch.setattr(wp_api.httpx, "get", lambda *a, **k: R(200, data))
    hits = wp_api.wp_search("x.ru", "q", 10, datetime(2026, 8, 1), datetime(2026, 9, 1))
    assert hits[0].title == "A & B" and hits[0].snippet == "hi"
    assert hits[0].published_at.year == 2026


def test_wp_search_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(wp_api.httpx, "get", lambda *a, **k: R(404, {}))
    assert wp_api.wp_search("x.ru", "q") is None


def test_wp_search_empty_list_is_authoritative(monkeypatch):
    monkeypatch.setattr(wp_api.httpx, "get", lambda *a, **k: R(200, []))
    assert wp_api.wp_search("x.ru", "q") == []

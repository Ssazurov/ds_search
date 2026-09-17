"""Тесты BraveProvider (issue #171, ADR-011)."""
import httpx
import pytest

from src.search import BraveProvider, QuotaExceeded


def test_brave_search_parses_hits(tmp_path, monkeypatch):
    provider = BraveProvider(api_key="fake", quota_path=tmp_path / "q.json")
    fake_json = {
        "web": {
            "results": [
                {"url": "https://x.org/a", "title": "A", "description": "snippet a"},
                {"url": "https://x.org/b", "title": "B", "description": "snippet b"},
            ]
        }
    }
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **kw: httpx.Response(
            200, json=fake_json, request=httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search")
        ),
    )
    hits = provider.search("синдром дауна раннее развитие")
    assert len(hits) == 2
    assert hits[0].url == "https://x.org/a"
    assert hits[0].title == "A"


def test_brave_sends_query_and_auth_header(tmp_path, monkeypatch):
    provider = BraveProvider(api_key="fake", quota_path=tmp_path / "q.json")
    requests = []

    def get(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(200, json={"web": {"results": []}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", get)
    provider.search("query", max_results=7)

    assert requests[0][0] == "https://api.search.brave.com/res/v1/web/search"
    assert requests[0][1]["params"] == {"q": "query", "count": 7}
    assert requests[0][1]["headers"]["X-Subscription-Token"] == "fake"


def test_brave_without_api_key_raises_quota_exceeded(monkeypatch, tmp_path):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    provider = BraveProvider(quota_path=tmp_path / "q.json")
    with pytest.raises(QuotaExceeded):
        provider.search("query")


def test_brave_does_not_consume_quota_on_api_error(tmp_path, monkeypatch):
    provider = BraveProvider(api_key="fake", quota_path=tmp_path / "q.json")
    response = httpx.Response(500, request=httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search"))
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response)

    with pytest.raises(httpx.HTTPStatusError):
        provider.search("query")
    assert provider.quota.used() == 0


@pytest.mark.parametrize("status_code", [401, 429])
def test_brave_maps_quota_http_errors(tmp_path, monkeypatch, status_code):
    provider = BraveProvider(api_key="fake", quota_path=tmp_path / "q.json")
    response = httpx.Response(
        status_code,
        request=httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search"),
    )
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: response)

    with pytest.raises(QuotaExceeded):
        provider.search("query")
    assert provider.quota.used() == 0


@pytest.mark.parametrize("query,max_results", [("", 10), ("  ", 10), ("query", 0), ("query", 101)])
def test_brave_rejects_invalid_search_arguments(tmp_path, query, max_results):
    provider = BraveProvider(api_key="fake", quota_path=tmp_path / "q.json")
    with pytest.raises(ValueError):
        provider.search(query, max_results=max_results)

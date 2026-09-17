"""Тесты FirecrawlProvider (issue #178, доп. к ADR-011)."""
import httpx
import pytest

from src.search import FirecrawlProvider, QuotaExceeded


def test_firecrawl_search_parses_hits(tmp_path, monkeypatch):
    provider = FirecrawlProvider(api_key="fake", quota_path=tmp_path / "q.json")
    fake_json = {
        "data": [
            {"url": "https://x.org/a", "title": "A", "description": "snippet a"},
            {"url": "https://x.org/b", "title": "B", "description": "snippet b"},
        ]
    }
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **kw: httpx.Response(
            200, json=fake_json, request=httpx.Request("POST", "https://api.firecrawl.dev/v1/search")
        ),
    )
    hits = provider.search("синдром дауна раннее развитие")
    assert len(hits) == 2
    assert hits[0].url == "https://x.org/a"
    assert hits[0].title == "A"


def test_firecrawl_sends_query_and_auth_header(tmp_path, monkeypatch):
    provider = FirecrawlProvider(api_key="fake", quota_path=tmp_path / "q.json")
    requests = []

    def post(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(200, json={"data": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    provider.search("query", max_results=7)

    assert requests[0][0] == "https://api.firecrawl.dev/v1/search"
    assert requests[0][1]["json"] == {"query": "query", "limit": 7}
    assert requests[0][1]["headers"]["Authorization"] == "Bearer fake"


def test_firecrawl_without_api_key_raises_quota_exceeded(monkeypatch, tmp_path):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    provider = FirecrawlProvider(quota_path=tmp_path / "q.json")
    with pytest.raises(QuotaExceeded):
        provider.search("query")


def test_firecrawl_does_not_consume_quota_on_api_error(tmp_path, monkeypatch):
    provider = FirecrawlProvider(api_key="fake", quota_path=tmp_path / "q.json")
    response = httpx.Response(500, request=httpx.Request("POST", "https://api.firecrawl.dev/v1/search"))
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: response)

    with pytest.raises(httpx.HTTPStatusError):
        provider.search("query")
    assert provider.quota.used() == 0


@pytest.mark.parametrize("status_code", [402, 429])
def test_firecrawl_maps_quota_http_errors(tmp_path, monkeypatch, status_code):
    provider = FirecrawlProvider(api_key="fake", quota_path=tmp_path / "q.json")
    response = httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://api.firecrawl.dev/v1/search"),
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: response)

    with pytest.raises(QuotaExceeded):
        provider.search("query")
    assert provider.quota.used() == 0


@pytest.mark.parametrize("query,max_results", [("", 10), ("  ", 10), ("query", 0), ("query", 101)])
def test_firecrawl_rejects_invalid_search_arguments(tmp_path, query, max_results):
    provider = FirecrawlProvider(api_key="fake", quota_path=tmp_path / "q.json")
    with pytest.raises(ValueError):
        provider.search(query, max_results=max_results)

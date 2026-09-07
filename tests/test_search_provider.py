"""Тесты search_provider (issue #15)."""
import httpx
import pytest

from src.search import QuotaExceeded, SearchProviderChain, TavilyProvider


def _mock_transport(json_response):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json_response)
    return httpx.MockTransport(handler)


def test_tavily_search_parses_hits(tmp_path, monkeypatch):
    provider = TavilyProvider(api_key="fake", quota_path=tmp_path / "q.json")
    fake_json = {
        "results": [
            {"url": "https://x.org/a", "title": "A", "content": "snippet a"},
            {"url": "https://x.org/b", "title": "B", "content": "snippet b"},
        ]
    }
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **kw: httpx.Response(200, json=fake_json, request=httpx.Request("POST", "https://api.tavily.com/search")),
    )
    hits = provider.search("синдром дауна раннее развитие")
    assert len(hits) == 2
    assert hits[0].url == "https://x.org/a"
    assert hits[0].title == "A"


def test_tavily_sends_query_and_max_results(tmp_path, monkeypatch):
    provider = TavilyProvider(api_key="fake", quota_path=tmp_path / "q.json")
    requests = []

    def post(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(200, json={"results": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    provider.search("query", max_results=7)

    assert requests[0][0] == "https://api.tavily.com/search"
    assert requests[0][1]["json"] == {"api_key": "fake", "query": "query", "max_results": 7}


def test_tavily_requires_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        TavilyProvider()


def test_tavily_does_not_consume_quota_on_api_error(tmp_path, monkeypatch):
    provider = TavilyProvider(api_key="fake", quota_path=tmp_path / "q.json")
    response = httpx.Response(500, request=httpx.Request("POST", "https://api.tavily.com/search"))
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: response)

    with pytest.raises(httpx.HTTPStatusError):
        provider.search("query")
    assert provider.quota.used() == 0


@pytest.mark.parametrize("status_code", [402, 429])
def test_tavily_maps_quota_http_errors(tmp_path, monkeypatch, status_code):
    provider = TavilyProvider(api_key="fake", quota_path=tmp_path / "q.json")
    response = httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: response)

    with pytest.raises(QuotaExceeded):
        provider.search("query")
    assert provider.quota.used() == 0


@pytest.mark.parametrize("query,max_results", [("", 10), ("  ", 10), ("query", 0), ("query", 101)])
def test_tavily_rejects_invalid_search_arguments(tmp_path, query, max_results):
    provider = TavilyProvider(api_key="fake", quota_path=tmp_path / "q.json")
    with pytest.raises(ValueError):
        provider.search(query, max_results=max_results)

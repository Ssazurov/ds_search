"""Тесты probe-этапа (issue #17)."""
import httpx
import pytest

from src.discovery.config import Settings
from src.discovery.gar_client import GarDiscoveryClient
from src.discovery.probe import _score_from_content, probe_source, run_probe_stage


def _settings(tmp_path=None) -> Settings:
    return Settings(
        core_api_url="https://gar.test",
        tenant_id=None,
        user_id="test",
        request_timeout_s=5.0,
        probe_max_bytes=2 * 1024 * 1024,
        probe_timeout_s=5.0,
    )


def test_score_none_for_thin_content():
    assert _score_from_content("короткий текст") is None


def test_score_low_for_catalog_listing():
    # много markdown-ссылок относительно текста -> высокий LTR
    md = " ".join(f"[ссылка на статью номер {i} с длинным текстом](url{i})" for i in range(30))
    score = _score_from_content(md)
    assert score == 0.1


def test_score_high_for_substantive_article():
    md = "Обычный текст статьи без ссылок. " * 100
    score = _score_from_content(md)
    assert score is not None
    assert score > 0.5


def test_probe_source_scores_substantive_html(monkeypatch):
    import asyncio
    asyncio.run(_probe_source_scores_substantive_html(monkeypatch))


async def _probe_source_scores_substantive_html(monkeypatch):
    html = "<html><body><p>" + "Статья про раннее развитие. " * 100 + "</p></body></html>"

    class FakeStream:
        def __init__(self, chunks):
            self._chunks = chunks
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
        def raise_for_status(self):
            pass
        @property
        def encoding(self):
            return "utf-8"
        async def aiter_bytes(self):
            for c in self._chunks:
                yield c

    class FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
        def stream(self, method, url):
            return FakeStream([html.encode("utf-8")])

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    outcome = await probe_source("https://example.org/a", _settings())
    assert outcome["probe_status"] == "scored"
    assert outcome["relevance_score"] > 0.5


def test_run_probe_stage_updates_only_scored(monkeypatch):
    calls = {"patched": []}

    class FakeClient:
        def __init__(self, settings):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def list_discovered_sources(self, status=None, domain=None):
            return [
                {"id": "1", "url": "https://example.org/good"},
                {"id": "2", "url": "https://example.org/thin"},
            ]
        def update_discovered_source(self, source_id, **fields):
            calls["patched"].append((source_id, fields))
            return {}

    import src.discovery.probe as probe_mod
    monkeypatch.setattr(probe_mod, "GarDiscoveryClient", FakeClient)

    async def fake_probe_source(url, settings):
        if "good" in url:
            return {"relevance_score": 0.9, "probe_status": "scored"}
        return {"relevance_score": None, "probe_status": "thin"}

    monkeypatch.setattr(probe_mod, "probe_source", fake_probe_source)

    import asyncio
    counts = asyncio.run(run_probe_stage(settings=_settings()))
    assert counts == {"scored": 1, "thin": 1, "error": 0}
    assert calls["patched"] == [("1", {"relevance_score": 0.9})]

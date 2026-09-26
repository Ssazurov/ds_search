"""issue #314: SourceCrawler.recrawl_url — override-параметры dest_dir/
filename/direction/category, объединяющие recrawl_url с download_single."""
import asyncio
import json
from pathlib import Path

import pytest

from src.crawler import crawler as crawler_mod
from src.crawler.config import SourceConfig
from src.crawler.crawler import SourceCrawler
from src.license.checker import LicenseCheckResult, LicenseStatus
from src.metadata import gar_schema

FIELDS = {
    "fields": [
        {"key": "age", "active": True, "required": True, "options": []},
        {"key": "doc_type", "active": True, "required": True, "options": []},
        {"key": "direction", "active": True, "required": True, "options": []},
        {"key": "category", "active": True, "required": True, "options": []},
    ]
}


def _license():
    return LicenseCheckResult(
        status=LicenseStatus.ATTRIBUTION_REQUIRED, reason="test",
        attribution_template="{title} {source_url}",
    )


class FakeResult:
    def __init__(self, success=True, html="", markdown="", metadata=None, url="https://example.org/a"):
        self.success = success
        self.html = html
        self.markdown = markdown
        self.metadata = metadata or {}
        self.url = url


class FakeCrawler:
    def __init__(self, result):
        self._result = result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def arun(self, url, config=None):
        return self._result


def _make_crawler(tmp_path: Path, monkeypatch, result: FakeResult) -> SourceCrawler:
    cfg = SourceConfig(
        name="test", domain="example.org", seed_urls=["https://example.org/"],
        keywords=[], direction="methodology", category="basic",
    )
    crawler = SourceCrawler(cfg, tmp_path / "out")
    monkeypatch.setattr(crawler_mod, "check_license", lambda domain, url: _license())
    monkeypatch.setattr(crawler_mod, "AsyncWebCrawler", lambda: FakeCrawler(result))
    monkeypatch.setattr(gar_schema, "load_gar_schema", lambda: FIELDS)
    monkeypatch.setattr(
        "src.crawler.crawler.classify_mod.classify",
        lambda title, text, fields, domain=None: {
            "age": "0-3", "doc_type": "article",
            "direction": "methodology", "category": "basic", "source": "llm",
        },
    )
    return crawler


def _substantive_result() -> FakeResult:
    return FakeResult(
        success=True, html="<html><body>обычная страница</body></html>",
        markdown="Содержательный материал про раннее развитие. " * 20,
        metadata={"title": "Заголовок"},
    )


def test_recrawl_url_without_kwargs_is_regression(tmp_path, monkeypatch):
    """Без override-параметров поведение как раньше: hash-based имя в out_dir."""
    crawler = _make_crawler(tmp_path, monkeypatch, _substantive_result())
    meta = asyncio.run(crawler.recrawl_url("https://example.org/a"))
    assert meta["content_status"] == "saved"
    from src.crawler.filters import canonicalize_url
    doc_id = __import__("hashlib").sha256(
        canonicalize_url("https://example.org/a").encode()
    ).hexdigest()[:16]
    expected = tmp_path / "out" / f"{doc_id}.md"
    assert expected.exists()
    assert meta["content_path"] == str(expected)


def test_recrawl_url_filename_override(tmp_path, monkeypatch):
    crawler = _make_crawler(tmp_path, monkeypatch, _substantive_result())
    meta = asyncio.run(crawler.recrawl_url("https://example.org/a", filename="custom name!"))
    expected = tmp_path / "out" / "custom_name.md"
    assert expected.exists()
    assert meta["content_path"] == str(expected)


def test_recrawl_url_dest_dir_override(tmp_path, monkeypatch):
    crawler = _make_crawler(tmp_path, monkeypatch, _substantive_result())
    meta = asyncio.run(crawler.recrawl_url("https://example.org/a", dest_dir="sub/dir"))
    assert (tmp_path / "out" / "sub" / "dir").is_dir()
    assert Path(meta["content_path"]).parent == tmp_path / "out" / "sub" / "dir"


@pytest.mark.parametrize("dest_dir", ["/tmp/outside", "../outside"])
def test_recrawl_url_rejects_destination_outside_out_dir(tmp_path, monkeypatch, dest_dir):
    crawler = _make_crawler(tmp_path, monkeypatch, _substantive_result())
    result = asyncio.run(crawler.recrawl_url("https://example.org/a", dest_dir=dest_dir))
    assert result is None
    # ничего не создано вне out_dir
    assert not (tmp_path / "outside").exists()


def test_recrawl_url_direction_category_override(tmp_path, monkeypatch):
    crawler = _make_crawler(tmp_path, monkeypatch, _substantive_result())
    meta = asyncio.run(crawler.recrawl_url(
        "https://example.org/a", direction="family_support", category="new_cat",
    ))
    assert meta["direction"] == "family_support"
    assert meta["category"] == "new_cat"
    # cfg не мутирован
    assert crawler.cfg.direction == "methodology"
    assert crawler.cfg.category == "basic"


def test_run_full_scan_unaffected_by_new_params(tmp_path, monkeypatch):
    """Регрессия: run() (full-scan) вызывает _save/_download_pdf без
    override-параметров, поведение не меняется."""
    crawler = _make_crawler(tmp_path, monkeypatch, _substantive_result())
    docs = asyncio.run(crawler.run())
    assert len(docs) == 1
    assert docs[0]["direction"] == "methodology"
    assert docs[0]["category"] == "basic"

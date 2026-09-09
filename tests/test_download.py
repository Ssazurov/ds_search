"""Тесты полного скачивания одной находки (issue #20 п.1, ADR-002 уточнения)."""
import asyncio
import json

import pytest

from src.discovery import download as dl
from src.license.checker import LicenseCheckResult, LicenseStatus


def _license(status=LicenseStatus.ATTRIBUTION_REQUIRED, downloadable=True):
    result = LicenseCheckResult(status=status, reason="test", attribution_template="{title} {source_url}")
    return result


class FakeResult:
    def __init__(self, success=True, html="", markdown="", metadata=None, error_message=""):
        self.success = success
        self.html = html
        self.markdown = markdown
        self.metadata = metadata or {}
        self.error_message = error_message
        self.url = "https://downsideup.org/a"


class FakeCrawler:
    def __init__(self, result):
        self._result = result
    async def __aenter__(self):
        return self
    async def __aexit__(self, *exc):
        return False
    async def arun(self, url, config=None):
        return self._result


def _patch_crawler(monkeypatch, result):
    monkeypatch.setattr(dl, "AsyncWebCrawler", lambda: FakeCrawler(result))


def test_doc_id_for_stable():
    a = dl.doc_id_for("https://downsideup.org/a/")
    b = dl.doc_id_for("https://downsideup.org/a")
    assert a == b
    assert len(a) == 16


def test_find_local_document_missing(tmp_path):
    assert dl.find_local_document("downsideup.org", "https://downsideup.org/a", tmp_path) is None


def test_find_local_document_found(tmp_path):
    domain_dir = tmp_path / "downsideup.org"
    domain_dir.mkdir()
    doc_id = dl.doc_id_for("https://downsideup.org/a")
    (domain_dir / f"{doc_id}.json").write_text(json.dumps({"content_status": "saved"}), encoding="utf-8")
    doc = dl.find_local_document("downsideup.org", "https://downsideup.org/a", tmp_path)
    assert doc == {"content_status": "saved"}


def test_download_single_license_deny(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "check_license", lambda domain, url: _license(LicenseStatus.DENY))
    source = {"url": "https://downsideup.org/a", "domain": "downsideup.org"}
    with pytest.raises(dl.DownloadError, match="license status"):
        asyncio.run(dl.download_single(source, tmp_path))


def test_download_single_substantive_saves_md(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "check_license", lambda domain, url: _license())
    html = "<html><body>обычная страница без формы</body></html>"
    result = FakeResult(success=True, html=html, markdown="Статья про раннее развитие. " * 50,
                         metadata={"title": "Заголовок"})
    _patch_crawler(monkeypatch, result)
    source = {"url": "https://downsideup.org/a", "domain": "downsideup.org", "suggested_direction": "methodology"}
    meta = asyncio.run(dl.download_single(source, tmp_path))
    assert meta["content_status"] == "saved"
    assert meta["title"] == "Заголовок"
    assert meta["category"] == "basic"
    assert meta["lifecycle_stage"] == "unspecified"
    assert meta["comorbidity_tags"] == ""
    assert meta["reviewed_by"] == ""
    assert len(meta["date_indexed"]) == 10
    assert (tmp_path / "downsideup.org" / f"{dl.doc_id_for('https://downsideup.org/a')}.md").exists()


def test_download_single_thin_without_pdf_link_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "check_license", lambda domain, url: _license())
    result = FakeResult(success=True, html="<html><body>коротко</body></html>", markdown="коротко")
    _patch_crawler(monkeypatch, result)
    source = {"url": "https://downsideup.org/a", "domain": "downsideup.org"}
    with pytest.raises(dl.DownloadError, match="thin content"):
        asyncio.run(dl.download_single(source, tmp_path))


def test_download_single_preserves_curated_information_architecture(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "check_license", lambda domain, url: _license())
    result = FakeResult(markdown="Содержательный материал. " * 50, metadata={"title": "Заголовок"})
    _patch_crawler(monkeypatch, result)
    meta = asyncio.run(dl.download_single({
        "url": "https://downsideup.org/a", "suggested_category": "comorbidities",
        "lifecycle_stage": "medical",
    }, tmp_path))
    assert meta["category"] == "comorbidities"
    assert meta["lifecycle_stage"] == "medical"


def test_download_single_fetch_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "check_license", lambda domain, url: _license())
    result = FakeResult(success=False, error_message="timeout")
    _patch_crawler(monkeypatch, result)
    source = {"url": "https://downsideup.org/a", "domain": "downsideup.org"}
    with pytest.raises(dl.DownloadError, match="fetch failed"):
        asyncio.run(dl.download_single(source, tmp_path))


def test_download_single_dest_dir_and_filename(monkeypatch, tmp_path):
    """issue #67: явная папка (относительно data_root) и имя файла."""
    monkeypatch.setattr(dl, "check_license", lambda domain, url: _license())
    html = "<html><body>обычная страница без формы</body></html>"
    result = FakeResult(success=True, html=html, markdown="Статья про раннее развитие. " * 50,
                         metadata={"title": "Заголовок"})
    _patch_crawler(monkeypatch, result)
    source = {"url": "https://downsideup.org/a", "suggested_direction": "methodology"}
    meta = asyncio.run(dl.download_single(
        source, tmp_path, dest_dir="custom/sub", filename="my article!",
    ))
    expected = tmp_path / "custom" / "sub" / "my_article.md"
    assert meta["content_path"] == str(expected)
    assert expected.exists()


def test_sanitize_filename_strips_unsafe_chars():
    assert dl._sanitize_filename("../../etc/passwd") == "passwd"
    assert dl._sanitize_filename("отчёт 2026.pdf") == "отчёт_2026"
    assert dl._sanitize_filename("   ") == "document"


@pytest.mark.parametrize("dest_dir", ["/tmp/outside", "../outside"])
def test_download_single_rejects_destination_outside_data_root(monkeypatch, tmp_path, dest_dir):
    """issue #67: dest_dir не должен позволять запись вне data_root
    (ни абсолютным путём, ни через .. )."""
    source = {"url": "https://downsideup.org/a"}

    with pytest.raises(dl.DownloadError, match="папка назначения"):
        asyncio.run(dl.download_single(source, tmp_path, dest_dir=dest_dir))

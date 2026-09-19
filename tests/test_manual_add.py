"""Тесты src/crawler/manual_add.py — добавление документа по URL (ADR-0014, issue #204)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from src.crawler import manual_add
from src.crawler.crawler import SourceCrawler
from src.license.checker import LicenseCheckResult, LicenseStatus


def _patch_license(monkeypatch, status: LicenseStatus, reason: str = "test"):
    def fake_check_license(domain, url, *a, **kw):
        return LicenseCheckResult(status=status, reason=reason)
    monkeypatch.setattr(manual_add, "check_license", fake_check_license)


def test_add_manual_document_success(tmp_path, monkeypatch):
    _patch_license(monkeypatch, LicenseStatus.ALLOW)

    async def fake_recrawl(self, url):
        doc_id = manual_add.hashlib.sha256(
            manual_add.canonicalize_url(url).encode()
        ).hexdigest()[:16]
        meta = {"source_url": url, "title": "Test", "content_path": str(self.out_dir / f"{doc_id}.md")}
        (self.out_dir / f"{doc_id}.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta

    monkeypatch.setattr(SourceCrawler, "recrawl_url", fake_recrawl)

    result = asyncio.run(manual_add.add_manual_document("https://newdomain.example/article", data_root=tmp_path))

    assert result["status"] == "added"
    assert result["source"] == "manual"
    assert (tmp_path / "manual" / f"{result['doc_id']}.json").exists()


def test_add_manual_document_unknown_domain_blocked(tmp_path, monkeypatch):
    _patch_license(monkeypatch, LicenseStatus.PENDING_MANUAL_REVIEW, reason="домен не в реестре")

    result = asyncio.run(manual_add.add_manual_document("https://unknown.example/page", data_root=tmp_path))

    assert result["status"] == "license_pending"
    assert not list((tmp_path).glob("**/*.json"))


def test_add_manual_document_duplicate_blocked(tmp_path, monkeypatch):
    _patch_license(monkeypatch, LicenseStatus.ALLOW)
    url = "https://dup.example/article"
    canon = manual_add.canonicalize_url(url)
    doc_id = manual_add.hashlib.sha256(canon.encode()).hexdigest()[:16]
    out_dir = tmp_path / "manual"
    out_dir.mkdir(parents=True)
    (out_dir / f"{doc_id}.json").write_text("{}", encoding="utf-8")

    called = False

    async def fake_recrawl(self, url):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(SourceCrawler, "recrawl_url", fake_recrawl)

    result = asyncio.run(manual_add.add_manual_document(url, data_root=tmp_path))

    assert result["status"] == "duplicate"
    assert result["doc_id"] == doc_id
    assert not called

"""Тесты revoke_document (issue #427)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.gar_ingest import documents
from src.gar_ingest.client import GarPublishError, PublishSettings


def _settings() -> PublishSettings:
    return PublishSettings(
        core_api_url="http://test", tenant_id=None, user_id="u",
        dataset_name="ds", request_timeout_s=1.0,
    )


class FakeClient:
    def __init__(self, fail: str | None = None):
        self.fail = fail
        self.delete_calls = []
        self.archive_calls = []

    def delete_document(self, document_id: str):
        self.delete_calls.append(document_id)
        if self.fail == "delete":
            raise GarPublishError("boom")
        if self.fail == "403":
            raise GarPublishError("403 Permission denied")

    def archive_document(self, document_id: str):
        self.archive_calls.append(document_id)
        if self.fail == "archive":
            raise GarPublishError("archive boom")


def _write_doc(tmp_path: Path, **overrides) -> Path:
    content_path = tmp_path / "article.md"
    content_path.write_text("# Title\n\nBody\n", encoding="utf-8")
    data = {
        "source_url": "https://example.org/a",
        "source_domain": "example.org",
        "title": "Article",
        "license": "attribution_required",
        "category": "family_support",
        "content_path": str(content_path),
        "content_status": "saved",
        "gar_document_id": "doc-1",
    }
    data.update(overrides)
    doc_json = tmp_path / "article.json"
    doc_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return doc_json


def test_revoke_document_success(tmp_path):
    doc_json = _write_doc(tmp_path)
    client = FakeClient()
    result = documents.revoke_document(doc_json, settings=_settings(), client=client)

    assert result == {
        "skipped": False,
        "doc_json_path": str(doc_json),
        "gar_document_id": "doc-1",
    }
    assert client.delete_calls == ["doc-1"]
    assert client.archive_calls == []

    saved = json.loads(doc_json.read_text(encoding="utf-8"))
    assert saved["gar_document_id"] is None
    assert saved["content_status"] == "revoked"


def test_revoke_document_skips_when_not_ingested(tmp_path):
    doc_json = _write_doc(tmp_path, gar_document_id=None)
    client = FakeClient()
    result = documents.revoke_document(doc_json, settings=_settings(), client=client)

    assert result == {"skipped": True, "doc_json_path": str(doc_json)}
    assert client.delete_calls == []
    assert client.archive_calls == []


def test_revoke_document_fallback_archive_on_403(tmp_path):
    doc_json = _write_doc(tmp_path)
    client = FakeClient(fail="403")
    result = documents.revoke_document(doc_json, settings=_settings(), client=client)

    assert result == {
        "skipped": False,
        "doc_json_path": str(doc_json),
        "gar_document_id": "doc-1",
        "archived_fallback": True,
    }
    assert client.delete_calls == ["doc-1"]
    assert client.archive_calls == ["doc-1"]

    saved = json.loads(doc_json.read_text(encoding="utf-8"))
    assert saved["gar_document_id"] is None
    assert saved["content_status"] == "revoked"


def test_revoke_document_raises_on_non_403_error(tmp_path):
    doc_json = _write_doc(tmp_path)
    client = FakeClient(fail="delete")

    with pytest.raises(GarPublishError, match="boom"):
        documents.revoke_document(doc_json, settings=_settings(), client=client)

    assert client.delete_calls == ["doc-1"]
    assert client.archive_calls == []

    # sidecar не должен быть изменён при ошибке
    saved = json.loads(doc_json.read_text(encoding="utf-8"))
    assert saved["gar_document_id"] == "doc-1"
    assert saved["content_status"] == "saved"


def test_revoke_document_already_revoked_is_noop(tmp_path):
    """Повторный revoke для уже отозванного документа (gar_document_id=None) — no-op."""
    doc_json = _write_doc(tmp_path, gar_document_id=None, content_status="revoked")
    client = FakeClient()
    result = documents.revoke_document(doc_json, settings=_settings(), client=client)

    assert result["skipped"] is True
    assert client.delete_calls == []

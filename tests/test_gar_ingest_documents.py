"""Тесты ingest_document (issue #115, ADR-006 п.3)."""
from __future__ import annotations

import json

import pytest

from src.gar_ingest import documents
from src.gar_ingest.client import GarPublishError, PublishSettings


def _settings() -> PublishSettings:
    return PublishSettings(
        core_api_url="http://test", tenant_id=None, user_id="u",
        dataset_name="ds", request_timeout_s=1.0,
    )


class FakeClient:
    def __init__(self, dataset_id="ds-1", document_id="doc-1", fail=False):
        self.dataset_id = dataset_id
        self.document_id = document_id
        self.fail = fail
        self.ingest_calls = []

    def ensure_dataset(self, name):
        return self.dataset_id

    def ingest_document(self, dataset_id, file_path, doc_name, metadata):
        self.ingest_calls.append((dataset_id, file_path, doc_name, metadata))
        if self.fail:
            raise GarPublishError("boom")
        return {"document_id": self.document_id}


def _write_doc(tmp_path, **overrides):
    content_path = tmp_path / "article.md"
    content_path.write_text("# Title\n\nBody\n", encoding="utf-8")
    data = {
        "source_url": "https://example.org/a", "source_domain": "example.org",
        "title": "Article", "license": "attribution_required",
        "category": "family_support", "content_path": str(content_path),
        "content_status": "saved",
    }
    data.update(overrides)
    doc_json = tmp_path / "article.json"
    doc_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return doc_json


def test_ingest_document_success(tmp_path):
    doc_json = _write_doc(tmp_path)
    client = FakeClient()
    result = documents.ingest_document(doc_json, settings=_settings(), client=client)

    assert result == {"skipped": False, "doc_json_path": str(doc_json), "gar_document_id": "doc-1"}
    saved = json.loads(doc_json.read_text(encoding="utf-8"))
    assert saved["gar_document_id"] == "doc-1"
    assert saved["ingested_at"]
    assert saved["ingest_error"] is None
    # content_path/content_status не должны попадать в metadata ingestion
    _, _, _, metadata = client.ingest_calls[0]
    assert "content_path" not in metadata and "content_status" not in metadata
    assert metadata["title"] == "Article"


def test_ingest_document_skips_when_already_ingested(tmp_path):
    doc_json = _write_doc(tmp_path, gar_document_id="old-id")
    client = FakeClient()
    result = documents.ingest_document(doc_json, settings=_settings(), client=client)

    assert result == {"skipped": True, "doc_json_path": str(doc_json), "gar_document_id": "old-id"}
    assert client.ingest_calls == []


def test_ingest_document_force_reingests(tmp_path):
    doc_json = _write_doc(tmp_path, gar_document_id="old-id")
    client = FakeClient(document_id="new-id")
    result = documents.ingest_document(doc_json, force=True, settings=_settings(), client=client)

    assert result["skipped"] is False
    assert result["gar_document_id"] == "new-id"


def test_ingest_document_missing_content_path_raises(tmp_path):
    doc_json = tmp_path / "no_content.json"
    doc_json.write_text(json.dumps({"title": "T"}), encoding="utf-8")

    with pytest.raises(ValueError):
        documents.ingest_document(doc_json, settings=_settings(), client=FakeClient())


def test_ingest_document_writes_error_on_failure(tmp_path):
    doc_json = _write_doc(tmp_path)
    client = FakeClient(fail=True)

    with pytest.raises(GarPublishError):
        documents.ingest_document(doc_json, settings=_settings(), client=client)

    saved = json.loads(doc_json.read_text(encoding="utf-8"))
    assert saved["ingest_error"] == "boom"
    assert "gar_document_id" not in saved

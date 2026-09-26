"""Тесты для ui/documents_tab.py (issue #311, по итогам ревью эпика #294,
ADR-014). Покрывает перенесённые из «Материалов» функции: merge GAR-only
строк, архивацию, оба варианта удаления, ingestion-батч.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import streamlit as st

from src.gar_ingest.client import GarPublishError
import ui.documents_tab as documents_tab


@pytest.fixture(autouse=True)
def _reset_session_state():
    st.session_state.clear()
    yield
    st.session_state.clear()


class FakeGarClient:
    """Фейковый GarIngestClient (issue #311): один экземпляр на with-блок,
    но calls/fail_ids — общее состояние теста, задаётся через фикстуру."""

    calls: list[tuple] = []
    fail_ids: set[str] = set()

    def __init__(self, settings=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ensure_dataset(self, name):
        return "ds-1"

    def list_documents(self, dataset_id, status=None):
        return []

    def delete_document(self, document_id):
        self.calls.append(("delete", document_id))
        if document_id in self.fail_ids:
            raise GarPublishError("not found")
        return {}

    def archive_document(self, document_id):
        self.calls.append(("archive", document_id))
        return {}

    def unarchive_document(self, document_id):
        self.calls.append(("unarchive", document_id))
        return {}


@pytest.fixture
def fake_gar_client(monkeypatch):
    FakeGarClient.calls = []
    FakeGarClient.fail_ids = set()
    monkeypatch.setattr("src.gar_ingest.client.GarIngestClient", FakeGarClient)
    return FakeGarClient


def _write_meta(raw_root: Path, domain: str, doc_id: str, **overrides) -> Path:
    (raw_root / domain).mkdir(parents=True, exist_ok=True)
    data = {"content_status": "saved", "title": doc_id, "source_domain": domain}
    data.update(overrides)
    path = raw_root / domain / f"{doc_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------- _scan_raw

def test_scan_raw_statuses_and_skips(tmp_path, monkeypatch):
    raw_root, clean_root = tmp_path / "raw", tmp_path / "clean"
    monkeypatch.setattr(documents_tab, "RAW_ROOT", raw_root)
    monkeypatch.setattr(documents_tab, "CLEAN_ROOT", clean_root)

    _write_meta(raw_root, "a.org", "loaded_doc", gar_document_id="gid-1")
    _write_meta(raw_root, "a.org", "error_doc", ingest_error="422 boom")
    _write_meta(raw_root, "a.org", "pending_doc")
    _write_meta(raw_root, "a.org", "not_downloaded", content_status="pending")  # должен быть пропущен
    (raw_root / "a.org" / "broken.json").write_text("{not json", encoding="utf-8")  # должен быть пропущен
    (clean_root / "a.org").mkdir(parents=True)
    (clean_root / "a.org" / "loaded_doc.json").write_text("{}", encoding="utf-8")

    rows = {r["doc_id"]: r for r in documents_tab._scan_raw()}

    assert set(rows) == {"loaded_doc", "error_doc", "pending_doc"}
    assert rows["loaded_doc"]["status"] == "loaded" and rows["loaded_doc"]["clean"] is True
    assert rows["error_doc"]["status"] == "error" and rows["error_doc"]["clean"] is False
    assert rows["pending_doc"]["status"] == "pending"
    assert all(r["local"] for r in rows.values())


# ------------------------------------------------------------ _gar_only_rows

def test_gar_only_rows_dedups_and_maps_fields():
    local_rows = [{"gar_document_id": "gid-local"}]
    st.session_state["gar_docs_cache"] = {
        "gid-local": {"metadata": {"title": "Уже локальный"}, "status": "indexed"},
        "gid-extra": {
            "metadata": {"title": "Только в GAR", "source_domain": "b.org"},
            "status": "archived", "doc_type": "article",
        },
    }

    extra = documents_tab._gar_only_rows(local_rows)

    assert len(extra) == 1
    row = extra[0]
    assert row["gar_document_id"] == "gid-extra"
    assert row["title"] == "Только в GAR"
    assert row["domain"] == "b.org"
    assert row["local"] is False
    assert row["doc_json_path"] is None and row["content_path"] is None
    assert row["gar_status"] == "archived"


def test_gar_only_rows_empty_cache():
    assert documents_tab._gar_only_rows([{"gar_document_id": "x"}]) == []


# --------------------------------------------------------- _delete_local_only

def test_delete_local_only_removes_meta_content_and_clean_sidecar(tmp_path, monkeypatch):
    clean_root = tmp_path / "clean"
    monkeypatch.setattr(documents_tab, "CLEAN_ROOT", clean_root)

    (tmp_path / "a.org").mkdir()
    content_path = tmp_path / "a.org" / "doc1.md"
    content_path.write_text("body", encoding="utf-8")
    doc_json_path = tmp_path / "a.org" / "doc1.json"
    doc_json_path.write_text(json.dumps({"content_path": str(content_path)}), encoding="utf-8")
    (clean_root / "a.org").mkdir(parents=True)
    clean_path = clean_root / "a.org" / "doc1.json"
    clean_path.write_text("{}", encoding="utf-8")

    documents_tab._delete_local_only({"doc_id": "doc1", "doc_json_path": doc_json_path})

    assert not doc_json_path.exists()
    assert not content_path.exists()
    assert not clean_path.exists()


def test_delete_local_only_missing_content_path_is_noop_not_error(tmp_path):
    doc_json_path = tmp_path / "doc1.json"
    doc_json_path.write_text(json.dumps({}), encoding="utf-8")
    documents_tab._delete_local_only({"doc_id": "doc1", "doc_json_path": doc_json_path})
    assert not doc_json_path.exists()


# ----------------------------------------------------- удаление (issue #299)

def test_delete_from_gar_batch_does_not_touch_local_files(tmp_path, fake_gar_client):
    doc_json_path = tmp_path / "doc1.json"
    doc_json_path.write_text(json.dumps({}), encoding="utf-8")
    row = {"doc_id": "doc1", "gar_document_id": "gid-1", "doc_json_path": doc_json_path}

    documents_tab._delete_from_gar_batch([row])

    assert ("delete", "gid-1") in fake_gar_client.calls
    assert doc_json_path.exists()  # локальный файл не тронут


def test_delete_everywhere_batch_removes_local_and_gar(tmp_path, fake_gar_client):
    doc_json_path = tmp_path / "doc1.json"
    doc_json_path.write_text(json.dumps({}), encoding="utf-8")
    row = {"doc_id": "doc1", "gar_document_id": "gid-1", "doc_json_path": doc_json_path}

    documents_tab._delete_everywhere_batch([row])

    assert ("delete", "gid-1") in fake_gar_client.calls
    assert not doc_json_path.exists()


def test_delete_everywhere_batch_gar_already_gone_still_deletes_local(tmp_path, fake_gar_client):
    """ADR-014, риск 2: если в GAR документа уже нет — не ошибка, локальный
    файл всё равно удаляется."""
    fake_gar_client.fail_ids = {"gid-1"}
    doc_json_path = tmp_path / "doc1.json"
    doc_json_path.write_text(json.dumps({}), encoding="utf-8")
    row = {"doc_id": "doc1", "gar_document_id": "gid-1", "doc_json_path": doc_json_path}

    documents_tab._delete_everywhere_batch([row])

    assert not doc_json_path.exists()


def test_delete_everywhere_batch_local_only_row_skips_gar_call(fake_gar_client):
    """Строка без gar_document_id (никогда не грузилась в GAR) — GAR не трогаем."""
    row = {"doc_id": "doc1", "gar_document_id": None, "doc_json_path": None}
    documents_tab._delete_everywhere_batch([row])
    assert fake_gar_client.calls == []


# --------------------------------------------------------------- _archive_batch

def test_archive_batch_archive_and_unarchive(fake_gar_client):
    rows = [{"doc_id": "d1", "gar_document_id": "gid-1"}, {"doc_id": "d2", "gar_document_id": "gid-2"}]

    documents_tab._archive_batch(rows, archive=True)
    assert fake_gar_client.calls == [("archive", "gid-1"), ("archive", "gid-2")]

    fake_gar_client.calls = []
    documents_tab._archive_batch(rows, archive=False)
    assert fake_gar_client.calls == [("unarchive", "gid-1"), ("unarchive", "gid-2")]


# --------------------------------------------------------------- _ingest_batch

def test_ingest_batch_skips_already_loaded_and_collects_errors(monkeypatch):
    calls: list[str] = []

    def fake_ingest_document(doc_json_path):
        calls.append(doc_json_path)
        if doc_json_path == "bad.json":
            raise RuntimeError("boom")

    monkeypatch.setattr(documents_tab, "ingest_document", fake_ingest_document)

    rows = [
        {"doc_id": "already", "gar_document_id": "gid-1", "doc_json_path": "already.json"},
        {"doc_id": "ok", "gar_document_id": None, "doc_json_path": "ok.json"},
        {"doc_id": "bad", "gar_document_id": None, "doc_json_path": "bad.json"},
    ]

    documents_tab._ingest_batch(rows)

    assert calls == ["ok.json", "bad.json"]  # "already" пропущен


def test_ingest_batch_all_loaded_is_noop(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(documents_tab, "ingest_document", lambda p: calls.append(p))
    documents_tab._ingest_batch([{"doc_id": "d1", "gar_document_id": "gid-1", "doc_json_path": "d1.json"}])
    assert calls == []

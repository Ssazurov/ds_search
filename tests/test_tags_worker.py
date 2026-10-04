"""Тесты фонового джоба заполнения tags из keywords (issue ds_search#483,
ADR-0015/ADR-0028 п.5)."""
from __future__ import annotations

from src.metadata import tags_worker


class FakeClient:
    """Имитирует GarIngestClient: list_documents/patch_document_metadata без HTTP."""

    def __init__(self, docs, dataset_id="ds-1"):
        self.dataset_id = dataset_id
        self.docs = docs
        self.patch_calls = []
        self.closed = False

    def ensure_dataset(self, name):
        return self.dataset_id

    def list_documents(self, dataset_id, status="indexed"):
        assert dataset_id == self.dataset_id
        assert status == "indexed"
        return self.docs

    def patch_document_metadata(self, document_id, metadata):
        self.patch_calls.append((document_id, metadata))
        return {"document_id": document_id, "metadata": metadata}

    def close(self):
        self.closed = True


def test_process_dataset_fills_tags_from_keywords():
    docs = [
        {"document_id": "d1", "metadata": {"keywords": "Эпилепсия, Сон, сон"}},
        {"document_id": "d2", "metadata": {"keywords": "", "tags": ["уже"]}},
        {"document_id": "d3", "metadata": {}},
    ]
    client = FakeClient(docs)

    summary = tags_worker.process_dataset(dataset_name="ds", client=client)

    assert summary == {"processed": 3, "updated": 1, "skipped": 2, "errors": []}
    assert client.patch_calls == [("d1", {"tags": ["эпилепсия", "сон"]})]
    assert client.closed is False


def test_process_dataset_skips_existing_tags_without_force():
    docs = [{"document_id": "d1", "metadata": {"keywords": "a, b", "tags": ["a"]}}]
    client = FakeClient(docs)

    summary = tags_worker.process_dataset(client=client)

    assert summary["updated"] == 0
    assert summary["skipped"] == 1
    assert client.patch_calls == []


def test_process_dataset_force_overwrites_existing_tags():
    docs = [{"document_id": "d1", "metadata": {"keywords": "new, tag", "tags": ["old"]}}]
    client = FakeClient(docs)

    summary = tags_worker.process_dataset(client=client, force=True)

    assert summary["updated"] == 1
    assert client.patch_calls == [("d1", {"tags": ["new", "tag"]})]


def test_process_dataset_dry_run_does_not_patch():
    docs = [{"document_id": "d1", "metadata": {"keywords": "a, b"}}]
    client = FakeClient(docs)

    summary = tags_worker.process_dataset(client=client, dry_run=True)

    assert summary["updated"] == 1
    assert client.patch_calls == []


def test_process_dataset_respects_limit():
    docs = [
        {"document_id": f"d{i}", "metadata": {"keywords": f"kw{i}"}}
        for i in range(5)
    ]
    client = FakeClient(docs)

    summary = tags_worker.process_dataset(client=client, limit=2)

    assert summary["processed"] == 2
    assert summary["updated"] == 2

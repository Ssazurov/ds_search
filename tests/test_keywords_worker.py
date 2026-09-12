"""Тесты фонового джоба автозаполнения keywords (issue #110, ADR-007)."""
from __future__ import annotations

from unittest.mock import patch

from src.metadata import keywords_worker
from src.news.llm_draft import LlmConfig


def _llm_config() -> LlmConfig:
    return LlmConfig(
        provider="anthropic", model="m", endpoint="http://test",
        temperature=0.2, max_tokens=300,
        prompt_template="{title}\n{text}", timeout_s=1.0, api_key="k",
    )


class FakeClient:
    """Имитирует GarIngestClient (issue #110): list_documents/
    get_document_text/patch_document_metadata без реального HTTP."""

    def __init__(self, docs, texts=None, dataset_id="ds-1"):
        self.dataset_id = dataset_id
        self.docs = docs
        self.texts = texts or {}
        self.patch_calls = []
        self.closed = False

    def ensure_dataset(self, name):
        return self.dataset_id

    def list_documents(self, dataset_id, status="indexed"):
        assert dataset_id == self.dataset_id
        assert status == "indexed"
        return self.docs

    def get_document_text(self, document_id):
        return self.texts.get(document_id, "")

    def patch_document_metadata(self, document_id, metadata):
        self.patch_calls.append((document_id, metadata))
        return {"document_id": document_id, "metadata": metadata}

    def close(self):
        self.closed = True


def test_extract_keywords_parses_comma_list():
    with patch.object(keywords_worker, "call_llm", lambda p, c: " a, b ,c ,"):
        result = keywords_worker.extract_keywords("T", "text", _llm_config())
    assert result == "a, b, c"


def test_process_dataset_updates_docs_without_keywords():
    docs = [
        {"document_id": "d1", "doc_name": "n1", "metadata": {}},
        {"document_id": "d2", "doc_name": "n2", "metadata": {"keywords": "уже есть"}},
    ]
    client = FakeClient(docs, texts={"d1": "some article text"})

    with patch.object(keywords_worker, "call_llm", lambda p, c: "keyword1, keyword2"):
        summary = keywords_worker.process_dataset(
            dataset_name="ds", client=client, llm_config=_llm_config(),
        )

    assert summary == {"processed": 2, "updated": 1, "skipped": 1, "errors": []}
    assert client.patch_calls == [("d1", {"keywords": "keyword1, keyword2"})]
    assert client.closed is False  # клиент передан снаружи -- джоб его не закрывает


def test_process_dataset_skips_empty_text():
    docs = [{"document_id": "d1", "doc_name": "n1", "metadata": {}}]
    client = FakeClient(docs, texts={})  # нет ассета -> get_document_text вернёт ""

    with patch.object(keywords_worker, "call_llm", lambda p, c: "should not be called"):
        summary = keywords_worker.process_dataset(client=client, llm_config=_llm_config())

    assert summary["updated"] == 0
    assert summary["skipped"] == 1
    assert client.patch_calls == []


def test_process_dataset_force_overwrites_existing_keywords():
    docs = [{"document_id": "d1", "doc_name": "n1", "metadata": {"keywords": "old"}}]
    client = FakeClient(docs, texts={"d1": "text"})

    with patch.object(keywords_worker, "call_llm", lambda p, c: "new, keywords"):
        summary = keywords_worker.process_dataset(
            client=client, llm_config=_llm_config(), force=True,
        )

    assert summary["updated"] == 1
    assert client.patch_calls == [("d1", {"keywords": "new, keywords"})]


def test_process_dataset_dry_run_does_not_patch():
    docs = [{"document_id": "d1", "doc_name": "n1", "metadata": {}}]
    client = FakeClient(docs, texts={"d1": "text"})

    with patch.object(keywords_worker, "call_llm", lambda p, c: "kw1, kw2"):
        summary = keywords_worker.process_dataset(
            client=client, llm_config=_llm_config(), dry_run=True,
        )

    assert summary["updated"] == 1  # считается как "было бы обновлено"
    assert client.patch_calls == []


def test_process_dataset_collects_errors_without_stopping():
    docs = [
        {"document_id": "d1", "doc_name": "n1", "metadata": {}},
        {"document_id": "d2", "doc_name": "n2", "metadata": {}},
    ]
    client = FakeClient(docs, texts={"d1": "text1", "d2": "text2"})

    calls = {"n": 0}

    def flaky_llm(prompt, config):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("llm down")
        return "kw"

    with patch.object(keywords_worker, "call_llm", flaky_llm):
        summary = keywords_worker.process_dataset(client=client, llm_config=_llm_config())

    assert summary["processed"] == 2
    assert summary["updated"] == 1
    assert len(summary["errors"]) == 1
    assert summary["errors"][0]["document_id"] == "d1"


def test_process_dataset_respects_limit():
    docs = [
        {"document_id": f"d{i}", "doc_name": f"n{i}", "metadata": {}}
        for i in range(5)
    ]
    client = FakeClient(docs, texts={f"d{i}": "text" for i in range(5)})

    with patch.object(keywords_worker, "call_llm", lambda p, c: "kw"):
        summary = keywords_worker.process_dataset(client=client, llm_config=_llm_config(), limit=2)

    assert summary["processed"] == 2
    assert summary["updated"] == 2

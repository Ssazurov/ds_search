"""Тесты src/news/bulk_digest.py — массовая переработка статей корпуса в
пересказы (issue #422)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.news import bulk_digest, db
from src.news.llm_draft import NotRelevantError


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "news_test.db"
    db.init_db(p)
    return p


def _write_corpus_doc(
    root: Path, domain: str, slug: str, *, doc_type: str = "article",
    gar_document_id: str | None = "gid-1", source_url: str | None = None, text: str = "Текст статьи про СД.",
) -> Path:
    d = root / domain
    d.mkdir(parents=True, exist_ok=True)
    md_path = d / f"{slug}.md"
    md_path.write_text(text, encoding="utf-8")
    doc = {
        "source_url": source_url or f"https://{domain}/{slug}",
        "source_domain": domain,
        "title": f"Заголовок {slug}",
        "doc_type": doc_type,
        "content_path": str(md_path),
    }
    if gar_document_id:
        doc["gar_document_id"] = gar_document_id
    json_path = d / f"{slug}.json"
    json_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return json_path


def _draft_item(source: dict) -> dict:
    return {
        "source_url": source["source_url"],
        "source_name": source.get("source_name"),
        "title": "Пересказ: " + (source.get("title") or ""),
        "summary": "summary",
        "body_md": "body",
        "direction": None,
        "tags": [],
        "requires_review": True,
        "status": "draft",
        "format": "digest",
        "quotes": [],
        "overlap_max_run": 0,
        "overlap_ratio": 0.0,
        "source_text": source.get("text", ""),
    }


def test_excluded_domain_is_skipped(tmp_path, db_path, monkeypatch):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "pravmir.ru", "a")
    monkeypatch.setattr(bulk_digest, "generate_draft", lambda *a, **k: pytest.fail("не должен вызываться"))

    stats = bulk_digest.bulk_digest(
        data_root=root, db_path=db_path, excluded_domains={"pravmir.ru"},
    )

    assert stats.excluded_domain == 1
    assert stats.candidates_total == 0
    assert stats.drafted == 0
    assert db.list_news_items(db_path=db_path) == []


def test_not_published_in_gar_is_skipped(tmp_path, db_path):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "foma.ru", "a", gar_document_id=None)

    stats = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set())

    assert stats.not_published == 1
    assert stats.candidates_total == 0
    assert db.list_news_items(db_path=db_path) == []


def test_non_article_doc_type_is_ignored(tmp_path, db_path):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "foma.ru", "a", doc_type="glossary_term")

    stats = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set())

    assert stats.candidates_total == 0
    assert stats.not_published == 0


def test_dry_run_counts_without_calling_llm_or_writing(tmp_path, db_path, monkeypatch):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "foma.ru", "a")
    _write_corpus_doc(root, "foma.ru", "b")
    monkeypatch.setattr(bulk_digest, "generate_draft", lambda *a, **k: pytest.fail("не должен вызываться"))

    stats = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set(), dry_run=True)

    assert stats.dry_run is True
    assert stats.candidates_total == 2
    assert len(stats.titles) == 2
    assert stats.drafted == 0
    assert db.list_news_items(db_path=db_path) == []


def test_happy_path_drafts_and_marks_idempotent_on_rerun(tmp_path, db_path, monkeypatch):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "foma.ru", "a")
    monkeypatch.setattr(bulk_digest, "generate_draft", lambda source, config=None, **k: _draft_item(source))

    stats1 = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set())
    assert stats1.drafted == 1
    assert stats1.candidates_total == 1
    items = db.list_news_items(db_path=db_path)
    assert len(items) == 1
    assert items[0]["format"] == "digest"

    # Повторный прогон — идемпотентность (issue #422): уже созданный
    # source_url пропускается, LLM не вызывается второй раз.
    calls = {"n": 0}

    def fail_on_call(*a, **k):
        calls["n"] += 1
        return _draft_item(a[0])

    monkeypatch.setattr(bulk_digest, "generate_draft", fail_on_call)
    stats2 = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set())

    assert stats2.skipped_duplicate == 1
    assert stats2.drafted == 0
    assert calls["n"] == 0
    assert len(db.list_news_items(db_path=db_path)) == 1


def test_not_relevant_is_skipped(tmp_path, db_path, monkeypatch):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "foma.ru", "a")

    def not_relevant(*a, **k):
        raise NotRelevantError("не про СД/РАС")

    monkeypatch.setattr(bulk_digest, "generate_draft", not_relevant)

    stats = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set())

    assert stats.not_relevant == 1
    assert stats.drafted == 0
    assert db.list_news_items(db_path=db_path) == []


def test_llm_failure_does_not_stop_run(tmp_path, db_path, monkeypatch):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "foma.ru", "a")
    _write_corpus_doc(root, "foma.ru", "b")

    calls = {"n": 0}

    def maybe_fail(source, config=None, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("LLM недоступен")
        return _draft_item(source)

    monkeypatch.setattr(bulk_digest, "generate_draft", maybe_fail)

    stats = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set())

    assert stats.llm_failed == 1
    assert stats.drafted == 1


def test_limit_stops_llm_calls_and_leaves_rest_for_next_run(tmp_path, db_path, monkeypatch):
    root = tmp_path / "raw"
    for slug in ("a", "b", "c"):
        _write_corpus_doc(root, "foma.ru", slug)
    monkeypatch.setattr(bulk_digest, "generate_draft", lambda source, config=None, **k: _draft_item(source))

    stats = bulk_digest.bulk_digest(data_root=root, db_path=db_path, excluded_domains=set(), limit=1)

    assert stats.drafted == 1
    assert stats.limited == 2
    assert stats.candidates_total == 3
    assert len(db.list_news_items(db_path=db_path)) == 1


def test_progress_cb_called_for_each_processed_item(tmp_path, db_path, monkeypatch):
    root = tmp_path / "raw"
    _write_corpus_doc(root, "foma.ru", "a")
    monkeypatch.setattr(bulk_digest, "generate_draft", lambda source, config=None, **k: _draft_item(source))
    seen = []

    bulk_digest.bulk_digest(
        data_root=root, db_path=db_path, excluded_domains=set(),
        progress_cb=lambda n, title: seen.append((n, title)),
    )

    assert seen == [(1, "Заголовок a")]


def test_load_excluded_domains_from_yaml(tmp_path):
    cfg = tmp_path / "digest_bulk.yaml"
    cfg.write_text("excluded_domains:\n  - Foo.RU\n  - bar.ru\n", encoding="utf-8")

    domains = bulk_digest.load_excluded_domains(cfg)

    assert domains == {"foo.ru", "bar.ru"}


def test_load_excluded_domains_missing_file_returns_empty(tmp_path):
    assert bulk_digest.load_excluded_domains(tmp_path / "missing.yaml") == set()

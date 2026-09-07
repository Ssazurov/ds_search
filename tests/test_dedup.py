"""Тесты дедупликации находок (issue #18)."""
import json

from src.discovery.dedup import (
    dedup_candidates, loaded_document_urls, mark_duplicates, past_findings_urls,
)


def test_loaded_document_urls_reads_saved_only(tmp_path):
    (tmp_path / "src1").mkdir()
    (tmp_path / "src1" / "a.json").write_text(
        json.dumps({"source_url": "https://example.org/a/", "content_status": "saved"}),
        encoding="utf-8",
    )
    (tmp_path / "src1" / "b.json").write_text(
        json.dumps({"source_url": "https://example.org/b", "content_status": "rejected_thin_content"}),
        encoding="utf-8",
    )
    urls = loaded_document_urls(tmp_path)
    assert urls == {"https://example.org/a"}


def test_loaded_document_urls_missing_root_returns_empty(tmp_path):
    assert loaded_document_urls(tmp_path / "does-not-exist") == set()


def test_mark_duplicates_flags_known_normalized_url():
    candidates = [
        {"url": "https://example.org/a/?utm_source=x", "title": "A"},
        {"url": "https://example.org/c", "title": "C"},
    ]
    known = {"https://example.org/a"}
    result = mark_duplicates(candidates, known)
    assert result[0]["is_duplicate"] is True
    assert result[1]["is_duplicate"] is False


def test_past_findings_urls_covers_all_dup_statuses():
    class FakeClient:
        def list_discovered_sources(self, status=None, domain=None):
            return {
                "approved": [{"url": "https://example.org/appr"}],
                "rejected": [{"url": "https://example.org/rej"}],
                "downloaded": [{"url": "https://example.org/dl"}],
            }[status]

    urls = past_findings_urls(FakeClient())
    assert urls == {
        "https://example.org/appr",
        "https://example.org/rej",
        "https://example.org/dl",
    }


def test_dedup_candidates_combines_local_and_remote_sources(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps({"source_url": "https://example.org/local", "content_status": "saved"}),
        encoding="utf-8",
    )

    class FakeClient:
        def list_discovered_sources(self, status=None, domain=None):
            return [{"url": "https://example.org/remote"}] if status == "approved" else []

    candidates = [
        {"url": "https://example.org/local", "title": "L"},
        {"url": "https://example.org/remote", "title": "R"},
        {"url": "https://example.org/new", "title": "N"},
    ]
    result = dedup_candidates(candidates, data_root=tmp_path, client=FakeClient())
    flags = {c["url"]: c["is_duplicate"] for c in result}
    assert flags == {
        "https://example.org/local": True,
        "https://example.org/remote": True,
        "https://example.org/new": False,
    }

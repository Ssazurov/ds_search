"""issue #93: SourceCrawler._apply_classification — автозаполнение +
needs_review, не блокирующее сохранение."""
from pathlib import Path

import pytest

from src.crawler.config import SourceConfig
from src.crawler.crawler import SourceCrawler
from src.metadata import gar_schema


FIELDS = {
    "fields": [
        {"key": "age", "active": True, "required": True, "options": []},
        {"key": "target_audience", "active": True, "required": False, "options": []},
        {"key": "doc_type", "active": True, "required": True, "options": []},
        {"key": "direction", "active": True, "required": True, "options": []},
        {"key": "category", "active": True, "required": True, "options": []},
    ]
}


def _make_crawler(tmp_path: Path) -> SourceCrawler:
    cfg = SourceConfig(
        name="test", domain="example.org", seed_urls=["https://example.org/"],
        keywords=[],
    )
    return SourceCrawler(cfg, tmp_path)


def test_apply_classification_fills_fields_and_clears_needs_review(tmp_path, monkeypatch):
    crawler = _make_crawler(tmp_path)
    monkeypatch.setattr(gar_schema, "load_gar_schema", lambda: FIELDS)
    monkeypatch.setattr(
        "src.crawler.crawler.classify_mod.classify",
        lambda title, text, fields, domain=None: {
            "age": "0-3", "target_audience": "parents", "doc_type": "article",
            "direction": "methodology", "category": "basic",
            "needs_review": False, "source": "llm",
        },
    )
    meta = {"direction": "methodology", "category": "basic"}
    result = crawler._apply_classification(meta, "title", "text")
    assert result["age"] == "0-3"
    assert result["doc_type"] == "article"
    assert result["needs_review"] is False


def test_apply_classification_needs_review_when_field_missing(tmp_path, monkeypatch):
    crawler = _make_crawler(tmp_path)
    monkeypatch.setattr(gar_schema, "load_gar_schema", lambda: FIELDS)
    monkeypatch.setattr(
        "src.crawler.crawler.classify_mod.classify",
        lambda title, text, fields, domain=None: {
            "age": None, "target_audience": None, "doc_type": "article",
            "direction": "methodology", "category": "basic",
            "needs_review": True, "source": "fallback",
        },
    )
    meta = {"direction": "methodology", "category": "basic"}
    result = crawler._apply_classification(meta, "title", "text")
    assert result["needs_review"] is True
    assert "age" not in result or not result["age"]


def test_apply_classification_gar_unavailable_sets_needs_review(tmp_path, monkeypatch):
    crawler = _make_crawler(tmp_path)

    def _raise():
        raise gar_schema.GarSchemaError("недоступен")

    monkeypatch.setattr(gar_schema, "load_gar_schema", _raise)
    meta = {"direction": "methodology", "category": "basic"}
    result = crawler._apply_classification(meta, "title", "text")
    assert result["needs_review"] is True

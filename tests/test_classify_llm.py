"""Тесты src/metadata/classify.py (issue #91)."""
import json
from unittest.mock import patch

from src.metadata import classify

FIELDS = {
    "fields": [
        {"key": "age", "active": True, "options": [
            {"id": "a1", "value": "0-3", "active": True},
        ]},
        {"key": "target_audience", "active": True, "options": [
            {"id": "t1", "value": "parents", "active": True},
        ]},
        {"key": "direction", "active": True, "options": [
            {"id": "d1", "value": "podderzhka-semi", "active": True},
        ]},
        {"key": "category", "active": True, "options": [
            {"id": "c1", "value": "issledovaniya-i-opyt-semey", "active": True, "parent_option_id": "d1"},
        ]},
        {"key": "doc_type", "active": True, "options": [
            {"id": "dt1", "value": "article", "active": True},
        ]},
    ]
}

MAPPING = {
    "example.org": {"direction": "podderzhka-semi", "age": "0-3"},
}


def test_build_prompt_lists_allowed_options():
    prompt = classify.build_prompt(FIELDS, "Заголовок", "Текст статьи")
    assert "podderzhka-semi" in prompt
    assert "issledovaniya-i-opyt-semey" in prompt
    assert "Заголовок" in prompt


def _fake_llm(raw: dict):
    return lambda prompt, cfg: json.dumps(raw)


def test_classify_llm_success_all_valid():
    raw = {"age": "0-3", "target_audience": "parents", "direction": "podderzhka-semi",
           "category": "issledovaniya-i-opyt-semey", "doc_type": "article"}
    with patch.object(classify, "call_llm", _fake_llm(raw)), \
         patch.object(classify, "load_llm_config", lambda: object()):
        result = classify.classify("t", "text", FIELDS)
    assert result == {**raw, "needs_review": False, "source": "llm"}


def test_classify_llm_invalid_value_becomes_none_and_needs_review():
    raw = {"age": "0-3", "target_audience": "parents", "direction": "podderzhka-semi",
           "category": "not-real", "doc_type": "article"}
    with patch.object(classify, "call_llm", _fake_llm(raw)), \
         patch.object(classify, "load_llm_config", lambda: object()):
        result = classify.classify("t", "text", FIELDS)
    assert result["category"] is None
    assert result["needs_review"] is True
    assert result["source"] == "llm"


def test_classify_llm_error_falls_back_to_mapping():
    def boom(prompt, cfg):
        raise RuntimeError("timeout")
    with patch.object(classify, "call_llm", boom), \
         patch.object(classify, "load_llm_config", lambda: object()):
        result = classify.classify("t", "text", FIELDS, domain="example.org", mapping=MAPPING)
    assert result["direction"] == "podderzhka-semi"
    assert result["age"] == "0-3"
    assert result["source"] == "fallback"
    assert result["needs_review"] is True  # target_audience/category/doc_type не закрыты


def test_classify_llm_partial_result_topped_up_by_fallback():
    raw = {"age": None, "target_audience": "parents", "direction": "podderzhka-semi",
           "category": "issledovaniya-i-opyt-semey", "doc_type": "article"}
    with patch.object(classify, "call_llm", _fake_llm(raw)), \
         patch.object(classify, "load_llm_config", lambda: object()):
        result = classify.classify("t", "text", FIELDS, domain="example.org", mapping=MAPPING)
    assert result["age"] == "0-3"
    assert result["source"] == "llm+fallback"
    assert result["needs_review"] is False


def test_classify_no_domain_no_fallback_needs_review_true():
    def boom(prompt, cfg):
        raise RuntimeError("timeout")
    with patch.object(classify, "call_llm", boom), \
         patch.object(classify, "load_llm_config", lambda: object()):
        result = classify.classify("t", "text", FIELDS)
    assert result["source"] == "none"
    assert result["needs_review"] is True


def test_real_classify_llm_yaml_parses():
    cfg = classify.load_llm_config()
    assert cfg.provider in ("anthropic", "openai_compatible")

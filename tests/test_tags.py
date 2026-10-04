"""Тесты нормализации тегов (issue ds_search#483, ADR-0015/ADR-0028).
Зеркалит gar-core-api/tests/test_tags.py — правила должны совпадать."""
from __future__ import annotations

from src.metadata.tags import normalize_tag, normalize_tags


def test_normalize_tag_trims_lowercases_and_folds_yo():
    assert normalize_tag("  Эпилепсия  ") == "эпилепсия"
    assert normalize_tag("СОН") == "сон"
    assert normalize_tag("ё-тест") == "е-тест"


def test_normalize_tag_collapses_whitespace_and_truncates():
    assert normalize_tag("a   b") == "a b"
    assert normalize_tag("x" * 50) == "x" * 40


def test_normalize_tags_from_string_splits_on_comma_and_dedupes():
    assert normalize_tags("Эпилепсия, сон, Сон, ") == ["эпилепсия", "сон"]


def test_normalize_tags_from_list():
    assert normalize_tags(["a", "", "b", "a"]) == ["a", "b"]


def test_normalize_tags_caps_at_ten():
    assert len(normalize_tags([str(i) for i in range(20)])) == 10


def test_normalize_tags_empty_input():
    assert normalize_tags(None) == []
    assert normalize_tags("") == []
    assert normalize_tags([]) == []

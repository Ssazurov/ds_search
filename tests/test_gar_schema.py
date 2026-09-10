"""Тесты src/metadata/gar_schema.py (issue #89)."""
import json
import time

import pytest

from src.metadata import gar_schema

FAKE_FIELDS = {
    "fields": [
        {"key": "age", "active": True, "required": True, "options": [
            {"id": "opt-age-1", "value": "18+ лет", "active": True},
        ]},
        {"key": "direction", "active": True, "required": False, "options": [
            {"id": "dir-1", "value": "podderzhka-semi", "active": True},
        ]},
        {"key": "category", "active": True, "required": False, "options": [
            {"id": "cat-1", "value": "gore-i-utrata", "active": True, "parent_option_id": "dir-1"},
            {"id": "cat-2", "value": "inactive-cat", "active": False, "parent_option_id": "dir-1"},
        ]},
    ]
}


def test_field_options_returns_active_values_only():
    assert gar_schema.field_options(FAKE_FIELDS, "age") == ["18+ лет"]


def test_field_options_unknown_key_returns_empty():
    assert gar_schema.field_options(FAKE_FIELDS, "unknown") == []


def test_category_options_for_direction_filters_by_parent():
    result = gar_schema.category_options_for_direction(FAKE_FIELDS, "podderzhka-semi")
    assert result == ["gore-i-utrata"]


def test_category_options_unknown_direction_returns_empty():
    assert gar_schema.category_options_for_direction(FAKE_FIELDS, "nope") == []


def test_required_field_keys():
    assert gar_schema.required_field_keys(FAKE_FIELDS) == ["age"]


def test_load_gar_schema_uses_fresh_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"fetched_at": time.time(), "fields": FAKE_FIELDS}), encoding="utf-8"
    )

    def fail_fetch(*args, **kwargs):
        raise AssertionError("не должен ходить в сеть при свежем кэше")

    monkeypatch.setattr(gar_schema, "fetch_gar_fields", fail_fetch)
    result = gar_schema.load_gar_schema(path=cache_path, ttl_seconds=3600)
    assert result == FAKE_FIELDS


def test_load_gar_schema_refetches_when_stale(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"fetched_at": time.time() - 999999, "fields": {"fields": []}}), encoding="utf-8"
    )
    monkeypatch.setattr(gar_schema, "fetch_gar_fields", lambda **kwargs: FAKE_FIELDS)
    result = gar_schema.load_gar_schema(path=cache_path, ttl_seconds=1)
    assert result == FAKE_FIELDS
    assert json.loads(cache_path.read_text())["fields"] == FAKE_FIELDS


def test_load_gar_schema_falls_back_to_stale_cache_on_network_error(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"fetched_at": 0, "fields": FAKE_FIELDS}), encoding="utf-8"
    )

    def boom(**kwargs):
        raise gar_schema.GarSchemaError("недоступен")

    monkeypatch.setattr(gar_schema, "fetch_gar_fields", boom)
    result = gar_schema.load_gar_schema(path=cache_path, ttl_seconds=1)
    assert result == FAKE_FIELDS


def test_load_gar_schema_raises_when_no_cache_and_network_fails(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"

    def boom(**kwargs):
        raise gar_schema.GarSchemaError("недоступен")

    monkeypatch.setattr(gar_schema, "fetch_gar_fields", boom)
    with pytest.raises(gar_schema.GarSchemaError):
        gar_schema.load_gar_schema(path=cache_path)

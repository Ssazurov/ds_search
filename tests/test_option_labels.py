from src.metadata.gar_schema import option_labels

FIELDS = {"fields": [
    {"key": "direction", "active": True, "options": [
        {"value": "zdorove", "label": "Здоровье", "active": True},
        {"value": "old", "label": "Старое", "active": False},
    ]},
    {"key": "age", "active": True, "options": [{"value": "Все возрасты", "active": True}]},
    {"key": "title", "active": True},
    {"key": "hidden", "active": False, "options": [{"value": "x", "label": "X"}]},
]}


def test_option_labels():
    labels = option_labels(FIELDS)
    assert labels["direction"] == {"zdorove": "Здоровье"}   # неактивные опции пропущены
    assert labels["age"] == {"Все возрасты": "Все возрасты"}  # нет label -> value
    assert "title" not in labels and "hidden" not in labels

from src.metadata import schema
from src.metadata.schema import label_of, load_dictionaries

GAR = {"fields": [
    {"key": "direction", "active": True, "options": [
        {"id": "d1", "value": "zdorove", "label": "Здоровье", "active": True}]},
    {"key": "category", "active": True, "options": [
        {"id": "c1", "value": "psihicheskoe-zdorove", "label": "Психическое здоровье",
         "active": True, "parent_option_id": "d1"}]},
]}


def test_label_of_fallback():
    d = {"labels": {"direction": {"zdorove": "Здоровье"}}}
    assert label_of(d, "direction", "zdorove") == "Здоровье"
    assert label_of(d, "direction", "unknown") == "unknown"
    assert label_of({}, "direction", "zdorove") == "zdorove"


def test_load_dictionaries_prefers_gar_cache(monkeypatch):
    monkeypatch.setattr(schema, "load_cache", lambda: {"fields": GAR})
    d = load_dictionaries()
    assert d["directions"] == {"zdorove": ["psihicheskoe-zdorove"]}
    assert label_of(d, "category", "psihicheskoe-zdorove") == "Психическое здоровье"


def test_load_dictionaries_without_cache_uses_yaml(monkeypatch):
    monkeypatch.setattr(schema, "load_cache", lambda: None)
    assert "directions" in load_dictionaries()

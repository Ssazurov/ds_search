"""sync_from_gar обновляет только кэш GAR-схемы, categories.yaml не трогает."""
from pathlib import Path

from src.metadata import sync_from_gar as mod

FIELDS = {"fields": [
    {"key": "direction", "options": [{"value": "zdorove", "active": True}]},
    {"key": "category", "options": [{"value": "a", "active": True, "parent": "zdorove"}]},
]}


def test_sync_refreshes_cache_not_yaml(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(mod, "load_gar_schema", lambda **k: calls.append(k) or FIELDS)
    monkeypatch.setattr(mod, "category_options_for_direction", lambda f, d: ["a"])
    monkeypatch.setattr(mod, "option_labels", lambda f: {})
    yaml_path = Path(mod.__file__).resolve().parents[2] / "config" / "categories.yaml"
    before = yaml_path.read_bytes() if yaml_path.exists() else None
    mod.sync_from_gar()
    assert calls == [{"force_refresh": True}]
    assert (yaml_path.read_bytes() if yaml_path.exists() else None) == before
    assert "кэш GAR обновлён" in capsys.readouterr().out

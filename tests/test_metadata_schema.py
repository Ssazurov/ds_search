"""Tests for the dictionaries contract used by the Streamlit UI."""
from pathlib import Path

import pytest
import yaml

from src.metadata.schema import load_dictionaries, save_dictionaries, validate_dictionaries


def _data() -> dict:
    return {
        "directions": {"methodology": ["speech_development"]},
        "doc_types": ["article"],
        "target_audiences": ["parents"],
        "age_groups": ["0-3"],
        "license_statuses": ["unknown", "allow"],
        "classifier_extra": {"keep": True},
    }


def test_validation_rejects_empty_invalid_and_duplicate_values():
    value = _data()
    value["directions"]["bad-name"] = []
    with pytest.raises(ValueError, match="идентификатор"):
        validate_dictionaries(value)
    value["directions"] = {"methodology": ["speech_development", "speech_development"]}
    with pytest.raises(ValueError, match="Дубликат категории"):
        validate_dictionaries(value)


def test_save_preserves_other_sections_and_round_trips(tmp_path: Path):
    path = tmp_path / "categories.yaml"
    path.write_text(yaml.safe_dump(_data(), sort_keys=False), encoding="utf-8")
    candidate = load_dictionaries(path)
    candidate["directions"]["neurodevelopment"] = ["attention"]
    candidate["directions"]["methodology"] = ["language"]
    save_dictionaries(candidate, path)
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert saved["directions"] == {"methodology": ["language"], "neurodevelopment": ["attention"]}
    assert saved["classifier_extra"] == {"keep": True}
    assert load_dictionaries(path)["directions"]["neurodevelopment"] == ["attention"]


def test_save_rejects_license_status_change_without_touching_file(tmp_path: Path):
    path = tmp_path / "categories.yaml"
    original = yaml.safe_dump(_data(), sort_keys=False)
    path.write_text(original, encoding="utf-8")
    candidate = load_dictionaries(path)
    candidate["license_statuses"] = ["deny"]
    with pytest.raises(ValueError, match="license_statuses"):
        save_dictionaries(candidate, path)
    assert path.read_text(encoding="utf-8") == original


def test_save_failure_removes_temporary_file_and_keeps_source(tmp_path: Path, monkeypatch):
    path = tmp_path / "categories.yaml"
    path.write_text(yaml.safe_dump(_data(), sort_keys=False), encoding="utf-8")
    candidate = load_dictionaries(path)
    candidate["directions"]["new_direction"] = []
    monkeypatch.setattr("src.metadata.schema.os.replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError, match="replace failed"):
        save_dictionaries(candidate, path)
    assert "new_direction" not in yaml.safe_load(path.read_text(encoding="utf-8"))["directions"]
    assert list(tmp_path.glob("*.tmp")) == []

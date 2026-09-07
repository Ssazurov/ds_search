"""Сохранённые пресеты параметров поиска (issue #19 п.2).

Локальный JSON, не бэкенд gar-core-api — пресеты нужны только внутри
ds_search UI, отдельного REST-ресурса под них не заводили (по аналогии с
data/search_quota.json из issue #15).
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "search_presets.json"


def load_presets(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_preset(preset: dict, path: Path = DEFAULT_PATH) -> list[dict]:
    """Добавляет/обновляет пресет по имени (preset['name']), возвращает
    полный список."""
    presets = load_presets(path)
    presets = [p for p in presets if p.get("name") != preset.get("name")]
    presets.append(preset)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)
    return presets


def delete_preset(name: str, path: Path = DEFAULT_PATH) -> list[dict]:
    presets = [p for p in load_presets(path) if p.get("name") != name]
    with path.open("w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)
    return presets

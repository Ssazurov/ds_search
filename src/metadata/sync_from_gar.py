"""Обратная синхронизация: GAR metadata-fields → config/categories.yaml.

Использование:
    cd ds_search && .venv/bin/python -m src.metadata.sync_from_gar [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

from .gar_schema import (
    GarSchemaError,
    load_gar_schema,
    field_options,
    category_options_for_direction,
)

_CATEGORIES_PATH = Path(__file__).resolve().parents[2] / "config" / "categories.yaml"


def _build_directions(fields: dict) -> dict[str, list[str]]:
    """Extract directions + categories from GAR schema."""
    direction_field = next((f for f in fields.get("fields", []) if f["key"] == "direction"), None)
    category_field = next((f for f in fields.get("fields", []) if f["key"] == "category"), None)
    if not direction_field or not category_field:
        raise GarSchemaError("в GAR нет полей direction/category")

    directions: dict[str, list[str]] = {}
    for opt in direction_field.get("options", []):
        if not opt.get("active", True):
            continue
        value = opt["value"]
        categories = category_options_for_direction(fields, value)
        directions[value] = categories
    return directions


def sync_from_gar(path: Path = _CATEGORIES_PATH, dry_run: bool = False) -> None:
    """Overwrite directions section in categories.yaml with GAR data."""
    fields = load_gar_schema(force_refresh=True)
    gar_directions = _build_directions(fields)

    original = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(original, dict):
        raise ValueError("categories.yaml root must be a map")

    original["directions"] = gar_directions

    if dry_run:
        print(json.dumps(gar_directions, ensure_ascii=False, indent=2))
        return

    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as f:
            temporary = f.name
            yaml.safe_dump(original, f, allow_unicode=True, sort_keys=False)
        with open(temporary, encoding="utf-8") as f:
            written = yaml.safe_load(f)
        if not isinstance(written, dict):
            raise ValueError("Сохранённый YAML должен быть объектом")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    print(f"OK: directions обновлены из GAR ({len(gar_directions)} направлений)")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Обратная синхронизация GAR → categories.yaml")
    parser.add_argument("--dry-run", action="store_true", help="только вывести JSON, не писать файл")
    args = parser.parse_args()
    try:
        sync_from_gar(dry_run=args.dry_run)
    except (GarSchemaError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()

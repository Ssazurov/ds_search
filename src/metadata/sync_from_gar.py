"""Обновление локального кэша GAR-схемы (config/gar_schema_cache.json, в .gitignore).

categories.yaml — статичный офлайн-фолбэк, сюда НЕ пишем: `load_dictionaries()`
накладывает directions+labels из кэша поверх (ADR-013).

Использование:
    cd ds_search && .venv/bin/python -m src.metadata.sync_from_gar [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys

from .gar_schema import (
    GarSchemaError,
    load_gar_schema,
    option_labels,
    category_options_for_direction,
)


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
        directions[value] = category_options_for_direction(fields, value)
    return directions


def sync_from_gar(dry_run: bool = False) -> None:
    """Принудительно обновить кэш GAR-схемы (dry_run — только вывести JSON)."""
    fields = load_gar_schema(force_refresh=True)  # fetch + save_cache
    gar_directions = _build_directions(fields)
    if dry_run:
        print(json.dumps({"directions": gar_directions, "labels": option_labels(fields)},
                         ensure_ascii=False, indent=2))
        return
    print(f"OK: кэш GAR обновлён ({len(gar_directions)} направлений)")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Обновить кэш GAR-схемы (categories.yaml не меняется)")
    parser.add_argument("--dry-run", action="store_true", help="только вывести JSON")
    args = parser.parse_args()
    try:
        sync_from_gar(dry_run=args.dry_run)
    except (GarSchemaError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()

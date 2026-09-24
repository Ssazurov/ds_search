"""Разовая миграция реестра источников config/licenses.yaml -> GAR (ds ADR-0021, #265).

Домены нормализуются (без www.), существующие в GAR НЕ перетираются.
По умолчанию dry-run; запись — с --apply.

  python scripts/migrate_registry_to_gar.py [--file PATH] [--apply]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.license.checker import normalize_domain  # noqa: E402
from src.license.registry_store import GarRegistryStore  # noqa: E402

FIELDS = ("status", "attribution_template", "notes", "checked_date", "publish_permission", "is_aggregator")


def plan(registry: dict, existing: set[str]) -> tuple[dict[str, dict], list[str]]:
    """-> (к записи {domain: fields}, пропущенные домены). Дубли www./без www.: побеждает канонический ключ."""
    todo: dict[str, dict] = {}
    canon = {d for d in registry if normalize_domain(d) == d}
    for raw, entry in registry.items():
        d = normalize_domain(raw)
        if raw != d and d in canon:
            continue
        entry = entry or {}
        todo[d] = {k: entry[k] for k in FIELDS if entry.get(k) is not None}
    skipped = sorted(d for d in todo if d in existing)
    return {d: v for d, v in todo.items() if d not in existing}, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "config" / "licenses.yaml"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    registry = yaml.safe_load(Path(args.file).read_text(encoding="utf-8")) or {}
    store = GarRegistryStore()
    existing = set(store.load_all())
    todo, skipped = plan(registry, existing)
    print(f"yaml: {len(registry)}, в GAR уже: {len(existing)}, к записи: {len(todo)}, пропущено (есть в GAR): {len(skipped)}")
    for d, v in sorted(todo.items()):
        print(f"  {'PUT' if args.apply else 'would PUT'} {d} status={v.get('status')}")
        if args.apply:
            store.put(d, v)
    if args.apply:
        print(f"итого в GAR: {len(store.load_all())}")


if __name__ == "__main__":
    main()

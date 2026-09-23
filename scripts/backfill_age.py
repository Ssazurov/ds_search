"""Backfill: проставить age в sidecar-json документов, где он пуст (issue #249).

Причина: ingest падал 422 "required field age must not be blank". Краулер теперь
ставит fallback сам; этот скрипт дочиняет уже собранные sidecar.

  python scripts/backfill_age.py            # dry-run: только отчёт
  python scripts/backfill_age.py --apply    # записать изменения
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.metadata.gar_schema import FALLBACK_AGE  # noqa: E402

AGE_ERROR_MARK = "age must not be blank"


def is_doc_sidecar(d: object) -> bool:
    return isinstance(d, dict) and "source_url" in d and "content_path" in d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"))
    args = ap.parse_args()

    total = fixed = 0
    for p in sorted(Path(args.raw_dir).rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not is_doc_sidecar(d):
            continue
        total += 1
        if str(d.get("age") or "").strip():
            continue
        d["age"] = FALLBACK_AGE
        d["needs_review"] = True
        if AGE_ERROR_MARK in str(d.get("ingest_error") or ""):
            d.pop("ingest_error")  # чужие ошибки ingest не трогаем
        fixed += 1
        print(("fix " if args.apply else "would fix ") + str(p.relative_to(args.raw_dir)))
        if args.apply:
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"sidecar: {total}, без age: {fixed}, {'записано' if args.apply else 'dry-run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

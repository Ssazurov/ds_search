#!/usr/bin/env python3
"""Разово дозаполняет author/publish_date/description в json family_support
из текстовой шапки статей downsideup.org и вырезает шапку из .md."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.metadata.downsideup_header import parse_header

FAMILY_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "family_support"


def main() -> None:
    updated = skipped_no_header = skipped_no_json = 0
    for md_path in sorted(FAMILY_DIR.glob("*.md")):
        json_path = md_path.with_suffix(".json")
        if not json_path.exists():
            skipped_no_json += 1
            continue
        text = md_path.read_text(encoding="utf-8")
        meta_add, body = parse_header(text)
        if not meta_add.get("publish_date"):
            skipped_no_header += 1
            continue
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        for key in ("author", "publish_date", "description"):
            if meta_add.get(key) and not meta.get(key):
                meta[key] = meta_add[key]
        json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(body, encoding="utf-8")
        updated += 1
    print(f"updated={updated} skipped_no_header={skipped_no_header} skipped_no_json={skipped_no_json}")


if __name__ == "__main__":
    main()

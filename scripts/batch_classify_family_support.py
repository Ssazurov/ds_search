"""Классифицировать все статьи в папке и обновить direction/category в JSON."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.classify_article import classify_article


def batch_classify(folder: Path) -> None:
    md_files = sorted(folder.glob("*.md"))
    updated = 0
    errors = 0
    for i, md_path in enumerate(md_files, 1):
        json_path = md_path.with_suffix(".json")
        if not json_path.exists():
            continue
        start = time.time()
        try:
            result = classify_article(md_path)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            data["direction"] = result["direction"]
            data["category"] = result["category"]
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            updated += 1
            print(
                f"[{i}/{len(md_files)}] {md_path.name}: "
                f"{result['direction']} / {result['category']} ({time.time() - start:.1f}s)"
            )
        except Exception as e:
            errors += 1
            print(
                f"[{i}/{len(md_files)}] {md_path.name}: ERROR {e} ({time.time() - start:.1f}s)"
            )

    print(f"\nГотово: обновлено {updated}, ошибок {errors}")


if __name__ == "__main__":
    batch_classify(Path("data/raw/family_support"))

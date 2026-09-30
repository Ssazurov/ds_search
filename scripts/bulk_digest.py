"""CLI: массовая переработка ранее загруженных статей корпуса в черновики-
пересказы (issue #422, эпик #419, подзадача C).

Использование:
    python -m scripts.bulk_digest --dry-run        # только посчитать кандидатов
    python -m scripts.bulk_digest --limit 20        # обработать не больше 20 за прогон
    python -m scripts.bulk_digest                   # без лимита — все кандидаты
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.news.bulk_digest import bulk_digest


def _progress(n: int, title: str) -> None:
    print(f"[{n}] {title}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="только посчитать кандидатов, не вызывать LLM")
    parser.add_argument("--limit", type=int, default=None, help="максимум статей за один прогон")
    args = parser.parse_args()

    stats = bulk_digest(dry_run=args.dry_run, limit=args.limit, progress_cb=_progress)
    for k, v in stats.as_dict().items():
        print(f"{k}={v}")
    if stats.dry_run and stats.titles:
        print("кандидаты:", file=sys.stderr)
        for t in stats.titles:
            print(f"  {t}", file=sys.stderr)
    if stats.errors:
        print(f"errors={len(stats.errors)}:", file=sys.stderr)
        for e in stats.errors:
            print(f"  {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

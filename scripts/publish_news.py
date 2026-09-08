"""CLI: публикует все news_items status=published без gar_document_id
в GAR (issue #49). Запуск вручную или по cron.

Использование: python -m scripts.publish_news [--force]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.news import db, publish


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="переопубликовать даже уже опубликованные")
    args = parser.parse_args()

    db.init_db()
    items = db.list_news_items(status="published")
    settings = publish.load_settings()
    ok, skipped, failed = 0, 0, 0
    with publish.GarNewsClient(settings) as client:
        for item in items:
            if item.get("gar_document_id") and not args.force:
                skipped += 1
                continue
            try:
                res = publish.publish_news_item(
                    item["id"], settings=settings, force=args.force, client=client,
                )
                print(f"[ok] id={item['id']} gar_document_id={res['gar_document_id']}")
                ok += 1
            except publish.GarPublishError as exc:
                print(f"[fail] id={item['id']}: {exc}", file=sys.stderr)
                failed += 1
    print(f"ok={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()

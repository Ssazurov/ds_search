"""Фоновое заполнение GAR-поля tags из keywords (issue ds_search#483,
ADR-0015/ADR-0028 п.5).

Источник значений tags вне скоупа ADR-0015 (отдельная задача) — здесь
простейший источник: уже заполненное keywords (text, через запятую,
issue #110) парсится в normalize_tags(). Документы без keywords
пропускаются — needs_review не затрагиваем, tags опционален.

CLI:
    .venv/bin/python -m src.metadata.tags_worker [--dataset NAME]
        [--limit N] [--force] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

from src.gar_ingest.client import GarIngestClient, GarPublishError, load_settings

from .tags import normalize_tags


def process_dataset(
    dataset_name: str | None = None, limit: int | None = None,
    force: bool = False, dry_run: bool = False,
    client: GarIngestClient | None = None,
) -> dict:
    """Проходит документы датасета, дозаполняет tags из keywords. Возвращает
    сводку {processed, updated, skipped, errors: [{document_id, error}]}."""
    settings = load_settings()
    dataset_name = dataset_name or settings.dataset_name
    owns_client = client is None
    client = client or GarIngestClient(settings)

    summary = {"processed": 0, "updated": 0, "skipped": 0, "errors": []}
    try:
        dataset_id = client.ensure_dataset(dataset_name)
        docs = client.list_documents(dataset_id, status="indexed")
        if limit is not None:
            docs = docs[:limit]

        for doc in docs:
            document_id = doc["document_id"]
            meta = doc.get("metadata") or {}
            summary["processed"] += 1

            if meta.get("tags") and not force:
                summary["skipped"] += 1
                continue

            tags = normalize_tags(meta.get("keywords"))
            if not tags:
                summary["skipped"] += 1
                continue

            try:
                if not dry_run:
                    client.patch_document_metadata(document_id, {"tags": tags})
                summary["updated"] += 1
            except (GarPublishError, Exception) as exc:  # noqa: BLE001 — джоб не должен падать на одном документе
                summary["errors"].append({"document_id": document_id, "error": str(exc)})
    finally:
        if owns_client:
            client.close()

    return summary


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Автозаполнение GAR tags из keywords фоновым джобом")
    parser.add_argument("--dataset", default=None, help="имя датасета (по умолчанию GAR_DATASET_NAME)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="перезаписать уже проставленные tags")
    parser.add_argument("--dry-run", action="store_true", help="только посчитать, не писать в GAR")
    args = parser.parse_args()

    summary = process_dataset(dataset_name=args.dataset, limit=args.limit, force=args.force, dry_run=args.dry_run)
    print(f"processed={summary['processed']} updated={summary['updated']} skipped={summary['skipped']} errors={len(summary['errors'])}")
    for err in summary["errors"]:
        print(f"  ERROR {err['document_id']}: {err['error']}", file=sys.stderr)
    sys.exit(1 if summary["errors"] else 0)


if __name__ == "__main__":
    _cli()

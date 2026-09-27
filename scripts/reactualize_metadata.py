"""Issue #303: реклассифицировать документы с деактивированным direction.

Находит документы, чей metadata.direction не входит в активные опции
GAR-схемы, прогоняет через classify() (живая схема) и PATCH'ит метадату.
Glossary/links-агрегаты (issue #303 п.4) сюда не входят — архивируются
отдельно вручную.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gar_ingest.client import GarIngestClient, load_settings
from src.metadata import classify as metadata_classify
from src.metadata import gar_schema

DATASET_ID = "81f35f18-8d32-458e-bf33-ddb68349e015"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", default=DATASET_ID)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--exclude-doc-type", action="append", default=[])
    args = parser.parse_args(argv)

    client = GarIngestClient(load_settings())
    fields = gar_schema.load_gar_schema(force_refresh=True)
    valid_directions = set(gar_schema.field_options(fields, "direction"))

    docs = client.list_documents(args.dataset_id, status="indexed")
    fixed, skipped = 0, 0
    for doc in docs:
        meta = doc.get("metadata") or {}
        direction = meta.get("direction")
        if direction in valid_directions:
            continue
        if meta.get("doc_type") in args.exclude_doc_type:
            skipped += 1
            continue
        document_id = doc["document_id"]
        title = meta.get("title") or doc.get("title") or ""
        domain = meta.get("source_domain") or ""
        text = client.get_document_text(document_id)
        result = metadata_classify.classify(title, text, fields, domain=domain)
        new_direction = result.get("direction")
        new_category = result.get("category")
        print(f"{document_id} [{direction!r} -> {new_direction!r}] {title[:60]}")
        if not args.dry_run and new_direction:
            client.patch_document_metadata(
                document_id, {"direction": new_direction, "category": new_category}
            )
            fixed += 1
    print(f"fixed={fixed} skipped={skipped} total={len(docs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

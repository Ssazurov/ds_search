#!/usr/bin/env python3
"""Backfill: нормализовать домен (без www.) у документов в GAR (issue #402).

После #400 source_domain нормализован без www., но в GAR у уже загруженных
документов домен мог остаться со старым значением. Скрипт находит такие
документы и обновляет metadata через PATCH /ingestion/documents/{id}.

Использование:
    python scripts/backfill_gar_domain.py              # dry-run по умолчанию
    python scripts/backfill_gar_domain.py --apply      # применить изменения
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

# Добавить src/ в PYTHONPATH для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gar_ingest.client import GarIngestClient, GarPublishError, load_settings


def normalize_domain(domain: str) -> str:
    """Убрать www. префикс из домена."""
    if domain.startswith("www."):
        return domain[4:]
    return domain


def extract_domain_from_url(url: str) -> str:
    """Извлечь нормализованный домен из URL."""
    return normalize_domain(urlparse(url).netloc)


def find_www_documents(client: GarIngestClient, dataset_id: str) -> list[dict]:
    """Найти все документы в GAR с доменом www.*."""
    docs = client.list_documents(dataset_id, status=None)
    www_docs = [
        d for d in docs
        if d.get("metadata", {}).get("source_domain", "").startswith("www.")
    ]
    return www_docs


def find_local_source(gar_document_id: str, db_path: Path) -> str | None:
    """Найти source_url для gar_document_id в news.db.
    
    Returns normalized domain from source_url, or None if not found.
    """
    if not db_path.exists():
        return None
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source_url FROM news_items WHERE gar_document_id = ?",
        (gar_document_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return extract_domain_from_url(row[0])
    return None


def backfill_domain(
    client: GarIngestClient,
    document_id: str,
    old_domain: str,
    new_domain: str,
    dry_run: bool = True
) -> bool:
    """Обновить source_domain у документа в GAR.
    
    Returns True if successful (or would be successful in dry-run).
    """
    if dry_run:
        print(f"  [DRY-RUN] Would update {document_id}: {old_domain} -> {new_domain}")
        return True
    
    try:
        client.patch_document_metadata(document_id, {"source_domain": new_domain})
        print(f"  [OK] Updated {document_id}: {old_domain} -> {new_domain}")
        return True
    except GarPublishError as exc:
        print(f"  [ERROR] Failed to update {document_id}: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Backfill: normalize domain (without www.) for documents in GAR"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)"
    )
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    if dry_run:
        print("=== DRY-RUN MODE (use --apply to make changes) ===\n")
    else:
        print("=== APPLYING CHANGES ===\n")
    
    # Load settings and connect to GAR
    settings = load_settings()
    db_path = Path(__file__).parent.parent / "data" / "news.db"
    
    with GarIngestClient(settings) as client:
        dataset_id = client.ensure_dataset(settings.dataset_name)
        www_docs = find_www_documents(client, dataset_id)
        
        print(f"Found {len(www_docs)} documents with www. domain in GAR\n")
        
        if not www_docs:
            print("No documents to update.")
            return
        
        # Group by domain for summary
        from collections import Counter
        domains = Counter(
            d.get("metadata", {}).get("source_domain", "") for d in www_docs
        )
        print("Documents by domain:")
        for domain, count in sorted(domains.items()):
            print(f"  {domain}: {count}")
        print()
        
        # Process each document
        updated = 0
        failed = 0
        
        for doc in www_docs:
            doc_id = doc["document_id"]
            old_domain = doc.get("metadata", {}).get("source_domain", "")
            new_domain = normalize_domain(old_domain)
            
            # Try to find local source for verification
            local_domain = find_local_source(doc_id, db_path)
            if local_domain and local_domain != new_domain:
                print(f"  [WARN] {doc_id}: normalized={new_domain} != local={local_domain}")
            
            success = backfill_domain(client, doc_id, old_domain, new_domain, dry_run)
            if success:
                updated += 1
            else:
                failed += 1
        
        print(f"\n=== Summary ===")
        print(f"Total documents: {len(www_docs)}")
        print(f"{'Would update' if dry_run else 'Updated'}: {updated}")
        if failed > 0:
            print(f"Failed: {failed}")
        
        if dry_run:
            print("\nRun with --apply to apply changes.")


if __name__ == "__main__":
    main()

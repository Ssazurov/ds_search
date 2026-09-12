"""Фоновый джоб автозаполнения GAR-поля keywords (issue #110, ADR-007).

Периодический процесс, отдельный от pre-upload пайплайна (download.py/
classify.py): читает уже загруженные в GAR документы датасета, для тех, у
кого metadata.keywords пусто, извлекает keywords из текста через LLM и
пишет их обратно через PATCH /ingestion/documents/{id} (мерж на сервере,
см. GarIngestClient.patch_document_metadata).

CLI:
    .venv/bin/python -m src.metadata.keywords_worker [--dataset NAME]
        [--limit N] [--force] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from src.gar_ingest.client import GarIngestClient, GarPublishError, load_settings
from src.news.llm_draft import LlmConfig, call_llm

_LLM_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "keywords_llm.yaml"
_MAX_TEXT_CHARS = 6000


def load_keywords_llm_config(path: Path = _LLM_CONFIG_PATH) -> LlmConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LlmConfig(
        provider=data["provider"], model=data["model"], endpoint=data["endpoint"],
        temperature=float(data.get("temperature", 0.2)),
        max_tokens=int(data.get("max_tokens", 300)),
        prompt_template=data.get("prompt_template", ""),
        timeout_s=float(data.get("timeout_s", 60.0)),
        api_key=str(data.get("api_key", "")),
    )


def extract_keywords(title: str, text: str, config: LlmConfig) -> str:
    """Возвращает строку keywords через запятую (GAR-поле text)."""
    prompt = config.prompt_template.format(title=title, text=text[:_MAX_TEXT_CHARS])
    raw = call_llm(prompt, config)
    return ", ".join(part.strip() for part in raw.strip().split(",") if part.strip())


def process_dataset(
    dataset_name: str | None = None, limit: int | None = None,
    force: bool = False, dry_run: bool = False,
    client: GarIngestClient | None = None, llm_config: LlmConfig | None = None,
) -> dict:
    """Проходит документы датасета, дозаполняет keywords. Возвращает
    сводку {processed, updated, skipped, errors: [{document_id, error}]}."""
    settings = load_settings()
    dataset_name = dataset_name or settings.dataset_name
    owns_client = client is None
    client = client or GarIngestClient(settings)
    llm_config = llm_config or load_keywords_llm_config()

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

            if meta.get("keywords") and not force:
                summary["skipped"] += 1
                continue

            try:
                text = client.get_document_text(document_id)
                if not text.strip():
                    summary["skipped"] += 1
                    continue
                keywords = extract_keywords(doc.get("doc_name", ""), text, llm_config)
                if not keywords:
                    summary["skipped"] += 1
                    continue
                if not dry_run:
                    client.patch_document_metadata(document_id, {"keywords": keywords})
                summary["updated"] += 1
            except (GarPublishError, Exception) as exc:  # noqa: BLE001 — джоб не должен падать на одном документе
                summary["errors"].append({"document_id": document_id, "error": str(exc)})
    finally:
        if owns_client:
            client.close()

    return summary


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Автозаполнение GAR keywords фоновым джобом")
    parser.add_argument("--dataset", default=None, help="имя датасета (по умолчанию GAR_DATASET_NAME)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="перезаписать уже проставленные keywords")
    parser.add_argument("--dry-run", action="store_true", help="только посчитать, не писать в GAR")
    args = parser.parse_args()

    summary = process_dataset(dataset_name=args.dataset, limit=args.limit, force=args.force, dry_run=args.dry_run)
    print(f"processed={summary['processed']} updated={summary['updated']} skipped={summary['skipped']} errors={len(summary['errors'])}")
    for err in summary["errors"]:
        print(f"  ERROR {err['document_id']}: {err['error']}", file=sys.stderr)
    sys.exit(1 if summary["errors"] else 0)


if __name__ == "__main__":
    _cli()

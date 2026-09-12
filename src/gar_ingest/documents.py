"""Ingestion одного corpus-документа (sidecar .json в data/raw/**) в GAR
(issue #115, ADR-006 п.3).

Файл .json — источник состояния (нет отдельной таблицы docs, в отличие от
news_items): ingest_document() пишет gar_document_id/ingested_at/
ingest_error обратно в тот же .json рядом с исходными полями профиля
(build_ingestion_metadata, ADR-002).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .client import GarIngestClient, GarPublishError, PublishSettings, load_settings

# Служебные поля sidecar .json, которые не публикуются в GAR как метаданные.
_NON_METADATA_KEYS = {
    "content_path", "content_status", "gar_document_id", "ingested_at",
    "ingest_error",
}


def _load(doc_json_path: Path) -> dict:
    with doc_json_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(doc_json_path: Path, data: dict) -> None:
    with doc_json_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def build_metadata(item: dict) -> dict:
    """Метаданные документа = поля sidecar .json за вычетом служебных."""
    return {k: v for k, v in item.items() if k not in _NON_METADATA_KEYS and v is not None}


def ingest_document(
    doc_json_path: Path | str, force: bool = False,
    settings: PublishSettings | None = None, client: GarIngestClient | None = None,
) -> dict:
    """Загружает content_path документа в GAR, обновляет sidecar .json.

    Идемпотентно (как publish_news_item): skip если gar_document_id уже
    есть и force=False. Ошибка ingestion пишется в ingest_error и
    пробрасывается вызывающему.
    """
    doc_json_path = Path(doc_json_path)
    item = _load(doc_json_path)

    if item.get("gar_document_id") and not force:
        return {"skipped": True, "doc_json_path": str(doc_json_path), "gar_document_id": item["gar_document_id"]}

    content_path = item.get("content_path")
    if not content_path:
        raise ValueError(f"{doc_json_path}: content_path отсутствует")
    file_path = Path(content_path)
    if not file_path.exists():
        raise FileNotFoundError(f"{doc_json_path}: content_path не найден: {file_path}")

    settings = settings or load_settings()
    owns_client = client is None
    client = client or GarIngestClient(settings)
    try:
        metadata = build_metadata(item)
        dataset_id = client.ensure_dataset(settings.dataset_name)
        result = client.ingest_document(
            dataset_id=dataset_id, file_path=file_path,
            doc_name=item.get("title") or file_path.stem, metadata=metadata,
        )
        document_id = result.get("document_id")
        item["gar_document_id"] = document_id
        item["ingested_at"] = datetime.now(timezone.utc).isoformat()
        item["ingest_error"] = None
        _save(doc_json_path, item)
        return {"skipped": False, "doc_json_path": str(doc_json_path), "gar_document_id": document_id}
    except GarPublishError as exc:
        item["ingest_error"] = str(exc)
        _save(doc_json_path, item)
        raise
    finally:
        if owns_client:
            client.close()

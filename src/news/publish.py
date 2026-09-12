"""Publish-адаптер news_items -> GAR ingestion, doc_type=news (issue #49,
ADR-003).

ds_site свой контент не хранит — читает материалы через GAR API/RAG (см.
ds_site/README.md). Поэтому "публикация в ds_site" технически сводится к
ingestion в GAR: как только новость проиндексирована с doc_type=news,
ds_site видит её через тот же поиск/RAG, что и остальной корпус. Отдельный
push-запрос в ds_site не нужен, пока сайт не хранит свой контент.

Идемпотентность: news_items.gar_document_id (issue #49-миграция в db.py) —
повторный запуск publish_news_item на уже опубликованный item — no-op.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from . import db
from ..metadata.profile import build_ingestion_metadata
from ..gar_ingest.client import (
    GarIngestClient,
    GarPublishError,
    PublishSettings,
    load_settings,
)

# Обратная совместимость (issue #115, ADR-006 п.2): логика вынесена в
# gar_ingest/client.py, GarNewsClient — алиас на общий GarIngestClient.
GarNewsClient = GarIngestClient


def build_content_md(item: dict) -> str:
    """Markdown-документ для ingestion (Docling принимает .pdf/.md/.docx)."""
    body = item.get("body_md") or item.get("summary") or ""
    return f"# {item['title']}\n\n{body}\n"


def build_metadata(item: dict) -> dict:
    """Маппинг news_item -> доменный профиль метаданных GAR (issue #4/#5),
    doc_type=news (issue #49), license=own_generated (ADR-003)."""
    source_url = item["source_url"]
    metadata = build_ingestion_metadata(
        source_url=source_url, source_domain=urlparse(source_url).netloc,
        title=item["title"], license="own_generated", category=item.get("category"),
        lifecycle_stage=item.get("lifecycle_stage"), direction=item.get("direction", "news"),
        doc_type="news", description=item.get("summary"),
        publish_date=item.get("published_at") or item.get("source_published_at"),
    )
    if item.get("tags"):
        metadata["keywords"] = ", ".join(item["tags"])
    return {k: v for k, v in metadata.items() if v is not None}


def publish_news_item(
    item_id: int, settings: PublishSettings | None = None, db_path: Path = db.DB_PATH,
    force: bool = False, client: GarNewsClient | None = None,
) -> dict:
    """Публикует один news_item (status=published) в GAR как doc_type=news.

    Идемпотентно: если gar_document_id уже проставлен и force=False —
    no-op, возвращает {"skipped": True, ...}. Ошибки GAR пишутся в
    news_items.publish_error (не бросаются наверх молча — UI/CLI решают,
    что делать), поэтому GarPublishError всё же пробрасывается вызывающему
    после записи в БД.
    """
    item = db.get_news_item(item_id, db_path)
    if item is None:
        raise ValueError(f"news_item {item_id} not found")
    if item["status"] != "published":
        raise ValueError(f"news_item {item_id} status={item['status']!r}, expected 'published'")
    if item.get("gar_document_id") and not force:
        return {"skipped": True, "item_id": item_id, "gar_document_id": item["gar_document_id"]}

    settings = settings or load_settings()
    owns_client = client is None
    client = client or GarNewsClient(settings)
    try:
        content = build_content_md(item)
        metadata = build_metadata(item)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8",
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            dataset_id = client.ensure_dataset(settings.dataset_name)
            result = client.ingest_document(
                dataset_id=dataset_id, file_path=tmp_path,
                doc_name=item["title"], metadata=metadata,
            )
        finally:
            tmp_path.unlink(missing_ok=True)
        document_id = result.get("document_id")
        db.set_publish_result(item_id, gar_document_id=document_id, error=None, db_path=db_path)
        return {"skipped": False, "item_id": item_id, "gar_document_id": document_id}
    except GarPublishError as exc:
        db.set_publish_result(item_id, gar_document_id=None, error=str(exc), db_path=db_path)
        raise
    finally:
        if owns_client:
            client.close()

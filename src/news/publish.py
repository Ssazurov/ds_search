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
from ..metadata import classify as metadata_classify
from ..metadata import gar_schema
from ..gar_ingest.client import (
    GarIngestClient,
    GarPublishError,
    PublishSettings,
    load_settings,
)

# Обратная совместимость (issue #115, ADR-006 п.2): логика вынесена в
# gar_ingest/client.py, GarNewsClient — алиас на общий GarIngestClient.
GarNewsClient = GarIngestClient

# issue #186: age — required-поле в GAR-схеме; если LLM-классификация и
# per-source fallback (gar_mapping) не закрыли его, паблиш падает 422
# "age must not be blank". "Все возрасты" — безопасный дефолт для новостей
# (нет узкой возрастной привязки), как и для downsideup (ds_ingestion #3).
FALLBACK_AGE = gar_schema.FALLBACK_AGE


def build_content_md(item: dict) -> str:
    """Markdown-документ для ingestion (Docling принимает .pdf/.md/.docx)."""
    body = item.get("body_md") or item.get("summary") or ""
    return f"# {item['title']}\n\n{body}\n"


# issue #219: у ручных черновиков (manual:<uuid>) нет домена, а GAR требует непустой source_domain
MANUAL_SOURCE_DOMAIN = "manual"


def effective_source_url(item: dict) -> str:
    """Ссылка источника для GAR/сайта. У ручных черновиков source_url =
    manual:<uuid>; если в поле «Источник» введён http(s)-URL, берём его."""
    url = item["source_url"]
    name = (item.get("source_name") or "").strip()
    if url.startswith("manual:") and name.lower().startswith(("http://", "https://")):
        return name
    return url


def classify_item(item: dict) -> dict:
    """Классифицирует news_item через metadata/classify.classify() (issue
    #91/эпик #88): age/target_audience/direction/category/doc_type.
    При недоступности GAR-схемы (сеть/кэш) — не падает, возвращает {}
    (issue #181: багфикс-связка, а не хардзависимость)."""
    domain = urlparse(effective_source_url(item)).netloc
    try:
        fields = gar_schema.load_gar_schema()
    except Exception:
        return {}
    text = item.get("body_md") or item.get("summary") or ""
    return metadata_classify.classify(item["title"], text, fields, domain=domain)


def build_metadata(item: dict) -> dict:
    """Маппинг news_item -> доменный профиль метаданных GAR (issue #4/#5),
    doc_type=news (issue #49), license=own_generated (ADR-003). Поля
    age/target_audience/category довязаны через metadata/classify.classify()
    (issue #181); doc_type всегда "news" (ADR-003), явные значения item
    (item["category"]/item["direction"]) имеют приоритет над LLM."""
    source_url = effective_source_url(item)
    classified = classify_item(item)
    metadata = build_ingestion_metadata(
        source_url=source_url, source_domain=urlparse(source_url).netloc or MANUAL_SOURCE_DOMAIN,
        title=item["title"], license="own_generated",
        category=item.get("category") or classified.get("category"),
        lifecycle_stage=item.get("lifecycle_stage"),
        direction=item.get("direction") or classified.get("direction") or "news",
        doc_type="news",
        description=item.get("summary"),
        publish_date=item.get("published_at") or item.get("source_published_at"),
    )
    # age — required в GAR-схеме: если ни LLM, ни per-source fallback не
    # закрыли поле, подставляем FALLBACK_AGE, иначе publish падает 422
    # (issue #186). needs_review из classify() уже отмечает такие записи.
    metadata["age"] = classified.get("age") or FALLBACK_AGE
    if classified.get("target_audience"):
        metadata["target_audience"] = classified["target_audience"]
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


def revoke_news_item(
    item_id: int, settings: PublishSettings | None = None, db_path: Path = db.DB_PATH,
    client: GarNewsClient | None = None,
) -> dict:
    """Отзывает документ news_item из GAR (hard delete) перед удалением записи.

    No-op, если gar_document_id не проставлен (черновик не публиковался).
    Issue #202: если у сервисного аккаунта нет прав delete на датасете
    (403 Permission denied) — fallback на archive_document (скрывает из
    /public и retrieval, issue #133). Любая другая GarPublishError
    пробрасывается наверх — вызывающий (UI) решает, что делать (не удалять
    локальную запись, чтобы не потерять gar_document_id).
    """
    item = db.get_news_item(item_id, db_path)
    if item is None:
        raise ValueError(f"news_item {item_id} not found")
    document_id = item.get("gar_document_id")
    if not document_id:
        return {"skipped": True, "item_id": item_id}

    settings = settings or load_settings()
    client = client or GarNewsClient(settings)
    try:
        client.delete_document(document_id)
    except GarPublishError as exc:
        if "403" not in str(exc):
            raise
        client.archive_document(document_id)
        db.clear_gar_document_id(item_id, db_path=db_path)
        return {
            "skipped": False, "item_id": item_id, "gar_document_id": document_id,
            "archived_fallback": True,
        }
    db.clear_gar_document_id(item_id, db_path=db_path)
    return {"skipped": False, "item_id": item_id, "gar_document_id": document_id}

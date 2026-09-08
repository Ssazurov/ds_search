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

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from . import db


class GarPublishError(RuntimeError):
    """Ошибка при обращении к gar-core-api ingestion."""


@dataclass(frozen=True)
class PublishSettings:
    core_api_url: str
    tenant_id: str | None
    user_id: str
    dataset_name: str
    request_timeout_s: float


def load_settings() -> PublishSettings:
    return PublishSettings(
        core_api_url=os.environ.get("GAR_CORE_API_URL", "http://127.0.0.1:8100"),
        tenant_id=os.environ.get("GAR_TENANT_ID") or None,
        user_id=os.environ.get("GAR_USER_ID", "ds-search-news-publish"),
        dataset_name=os.environ.get("GAR_DATASET_NAME", "sindrom-dauna"),
        request_timeout_s=float(os.environ.get("GAR_REQUEST_TIMEOUT_S", "660")),
    )


class GarNewsClient:
    """Тонкий ingestion-клиент (по образцу ds_ingestion/src/gar_client/client.py
    — тот пакет не переиспользуем напрямую, т.к. это отдельный репозиторий/
    процесс без общего пакета)."""

    def __init__(self, settings: PublishSettings):
        headers = {"X-User-ID": settings.user_id}
        if settings.tenant_id:
            headers["X-Tenant-ID"] = settings.tenant_id
        self._client = httpx.Client(
            base_url=settings.core_api_url, headers=headers,
            timeout=httpx.Timeout(settings.request_timeout_s),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GarNewsClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def ensure_dataset(self, name: str) -> str:
        resp = self._client.get("/ingestion/datasets")
        resp.raise_for_status()
        for row in resp.json().get("datasets", []):
            if row["name"] == name:
                return row["id"]
        resp = self._client.post("/ingestion/datasets", json={"name": name})
        if resp.status_code not in (200, 201):
            raise GarPublishError(f"create dataset failed: {resp.status_code} {resp.text}")
        return resp.json()["dataset"]["id"]

    def ingest_document(self, dataset_id: str, file_path: Path, doc_name: str, metadata: dict) -> dict:
        import json as _json
        with file_path.open("rb") as fh:
            files = {"file": (file_path.name, fh)}
            data = {
                "dataset_id": dataset_id, "doc_name": doc_name,
                "metadata": _json.dumps(metadata, ensure_ascii=False),
            }
            resp = self._client.post("/ingestion/documents", data=data, files=files)
        if resp.status_code != 200:
            raise GarPublishError(f"ingest {file_path.name} failed: {resp.status_code} {resp.text}")
        return resp.json()


def build_content_md(item: dict) -> str:
    """Markdown-документ для ingestion (Docling принимает .pdf/.md/.docx)."""
    body = item.get("body_md") or item.get("summary") or ""
    return f"# {item['title']}\n\n{body}\n"


def build_metadata(item: dict) -> dict:
    """Маппинг news_item -> доменный профиль метаданных GAR (issue #4/#5),
    doc_type=news (issue #49), license=own_generated (ADR-003)."""
    source_url = item["source_url"]
    metadata = {
        "source_url": source_url,
        "source_domain": urlparse(source_url).netloc,
        "title": item["title"],
        "direction": item.get("direction", "news"),
        "doc_type": "news",
        "license": "own_generated",
        "description": item.get("summary"),
        "publish_date": item.get("published_at") or item.get("source_published_at"),
    }
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

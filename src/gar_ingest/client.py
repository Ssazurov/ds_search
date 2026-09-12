"""Общий HTTP-клиент ingestion в gar-core-api (ADR-006 п.2).

Вынесен из src/news/publish.py (GarNewsClient -> GarIngestClient), чтобы
переиспользовать в src/gar_ingest/documents.py без дублирования HTTP-логики.
Поведение news/publish.py не меняется — оно импортирует эти же классы.
"""
from __future__ import annotations

import json as _json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


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


class GarIngestClient:
    """Тонкий ingestion-клиент к gar-core-api (settings/ensure_dataset/
    ingest_document). Раньше жил в news/publish.py как GarNewsClient."""

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

    def __enter__(self) -> "GarIngestClient":
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

    def list_documents(self, dataset_id: str, status: str | None = "indexed") -> list[dict]:
        """GET /ingestion/documents?dataset_id=... (issue #110). status=None
        передаётся как пустая строка, чтобы получить все статусы, как в API."""
        params = {"dataset_id": dataset_id, "status": status or ""}
        resp = self._client.get("/ingestion/documents", params=params)
        if resp.status_code != 200:
            raise GarPublishError(f"list documents failed: {resp.status_code} {resp.text}")
        return resp.json().get("documents", [])

    def get_document_text(self, document_id: str) -> str:
        """Канонический markdown документа (assets/canonical-md) для анализа
        текста (issue #110). Пустая строка, если ассет недоступен (404)."""
        resp = self._client.get(f"/ingestion/documents/{document_id}/assets/canonical-md")
        if resp.status_code == 404:
            return ""
        if resp.status_code != 200:
            raise GarPublishError(f"get document text {document_id} failed: {resp.status_code} {resp.text}")
        return resp.text

    def patch_document_metadata(self, document_id: str, metadata: dict) -> dict:
        """PATCH /ingestion/documents/{id}: сервер мержит metadata с
        существующей (services/document_edit_service.update_document),
        так что здесь безопасно передавать только изменяемые поля."""
        resp = self._client.patch(f"/ingestion/documents/{document_id}", json={"metadata": metadata})
        if resp.status_code != 200:
            raise GarPublishError(f"patch document {document_id} failed: {resp.status_code} {resp.text}")
        return resp.json()

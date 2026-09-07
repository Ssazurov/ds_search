"""HTTP-клиент к discovery REST API gar-core-api (issue #17, ADR-002).

ds_search не пишет discovered_sources/search_runs напрямую в Postgres —
паттерн проекта (см. ds_ingestion/gar_client) требует REST-слой
gar-core-api для любого доступа к GAR (routers/discovery.py, PR #222)."""
from __future__ import annotations

import httpx

from .config import Settings


class GarDiscoveryClientError(RuntimeError):
    """Ошибка при обращении к discovery API gar-core-api."""


class GarDiscoveryClient:
    def __init__(self, settings: Settings):
        headers = {"X-User-ID": settings.user_id}
        if settings.tenant_id:
            headers["X-Tenant-ID"] = settings.tenant_id
        self._client = httpx.Client(
            base_url=settings.core_api_url,
            headers=headers,
            timeout=httpx.Timeout(settings.request_timeout_s),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GarDiscoveryClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def create_search_run(self, query: str, provider: str | None = None) -> dict:
        resp = self._client.post("/search-runs", json={"query": query, "provider": provider})
        if resp.status_code != 201:
            raise GarDiscoveryClientError(f"create search run failed: {resp.status_code} {resp.text}")
        return resp.json()

    def update_search_run(self, run_id: str, **fields) -> dict:
        resp = self._client.patch(f"/search-runs/{run_id}", json=fields)
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"update search run {run_id} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def upsert_discovered_sources(self, run_id: str, items: list[dict]) -> list[dict]:
        resp = self._client.post(f"/search-runs/{run_id}/discovered-sources", json={"items": items})
        if resp.status_code != 201:
            raise GarDiscoveryClientError(f"upsert discovered sources for run {run_id} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def list_discovered_sources(self, status: str | None = None, domain: str | None = None) -> list[dict]:
        params = {k: v for k, v in {"status": status, "domain": domain}.items() if v is not None}
        resp = self._client.get("/discovered-sources", params=params)
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"list discovered sources failed: {resp.status_code} {resp.text}")
        return resp.json()

    def update_discovered_source(self, source_id: str, **fields) -> dict:
        resp = self._client.patch(f"/discovered-sources/{source_id}", json=fields)
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"update discovered source {source_id} failed: {resp.status_code} {resp.text}")
        return resp.json()

"""HTTP-клиент к discovery REST API gar-core-api (issue #17, ADR-002).

ds_search не пишет discovered_sources/search_runs напрямую в Postgres —
паттерн проекта (см. ds_ingestion/gar_client) требует REST-слой
gar-core-api для любого доступа к GAR (routers/discovery.py, PR #222)."""
from __future__ import annotations

from urllib.parse import quote

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

    def list_search_runs(self, limit: int = 20) -> list[dict]:
        resp = self._client.get("/search-runs", params={"limit": limit})
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"list search runs failed: {resp.status_code} {resp.text}")
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

    def delete_discovered_source(self, source_id: str) -> None:
        resp = self._client.delete(f"/discovered-sources/{source_id}")
        if resp.status_code not in (200, 204):
            raise GarDiscoveryClientError(f"delete discovered source {source_id} failed: {resp.status_code} {resp.text}")

    # --- реестр источников (ds ADR-0021, gar-core-api /source-registry) ---

    def _registry_request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise GarDiscoveryClientError(f"{method} {path} failed: {exc}") from exc

    @staticmethod
    def _registry_path(domain: str, suffix: str = "") -> str:
        return f"/source-registry/{quote(domain, safe='')}{suffix}"

    def list_source_registry(self) -> list[dict]:
        resp = self._registry_request("GET", "/source-registry")
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"list source registry failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_source_registry_entry(self, domain: str) -> dict | None:
        """Запись реестра по домену; None, если домена в реестре нет (404)."""
        resp = self._registry_request("GET", self._registry_path(domain))
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"get source registry {domain} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def put_source_registry_entry(self, domain: str, **fields) -> dict:
        resp = self._registry_request("PUT", self._registry_path(domain), json=fields)
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"put source registry {domain} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def ensure_source_registry_entry(self, domain: str, attribution_template: str = "") -> dict:
        """Атомарно создаёт pending_manual_review, только если записи нет (существующую не трогает)."""
        resp = self._registry_request(
            "POST", self._registry_path(domain, "/ensure"), json={"attribution_template": attribution_template},
        )
        if resp.status_code not in (200, 201):
            raise GarDiscoveryClientError(f"ensure source registry {domain} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def delete_source_registry_entry(self, domain: str) -> None:
        resp = self._registry_request("DELETE", self._registry_path(domain))
        if resp.status_code not in (200, 204, 404):
            raise GarDiscoveryClientError(f"delete source registry {domain} failed: {resp.status_code} {resp.text}")

    def source_registry_history(self, domain: str, limit: int = 50) -> list[dict]:
        resp = self._registry_request("GET", self._registry_path(domain, "/history"), params={"limit": limit})
        if resp.status_code != 200:
            raise GarDiscoveryClientError(f"source registry history {domain} failed: {resp.status_code} {resp.text}")
        return resp.json()

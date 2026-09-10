"""Синхронизация схемы metadata-fields из GAR core-api (issue #89, эпик #88).

Схема словаря метаданных (direction/category/age/target_audience/doc_type и
т.д.) — источник правды находится в GAR (база sindrom-dauna), не в локальных
константах ds_search. Этот модуль тянет её через
GET /datasets/{dataset_id}/metadata-fields и кэширует локально, чтобы
краулер не зависел от доступности gar-core-api при каждом запуске.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

DEFAULT_CORE_API_URL = os.environ.get("GAR_CORE_API_URL", "http://localhost:8100")
DEFAULT_USER_ID = os.environ.get("GAR_USER_ID", "admin-ui")
DEFAULT_TENANT_ID = os.environ.get("GAR_TENANT_ID")
DEFAULT_DATASET_NAME = os.environ.get("GAR_DATASET_NAME", "sindrom-dauna")
DEFAULT_DATASET_ID = os.environ.get("GAR_DATASET_ID")

_CACHE_PATH = Path(__file__).resolve().parents[2] / "config" / "gar_schema_cache.json"
DEFAULT_TTL_SECONDS = 24 * 3600


class GarSchemaError(RuntimeError):
    """Не удалось получить/прочитать схему GAR (сеть, 403, битый кэш)."""


def _headers() -> dict:
    headers = {"X-User-ID": DEFAULT_USER_ID}
    if DEFAULT_TENANT_ID:
        headers["X-Tenant-ID"] = DEFAULT_TENANT_ID
    return headers


def resolve_dataset_id(name: str = DEFAULT_DATASET_NAME, core_api_url: str = DEFAULT_CORE_API_URL) -> str:
    """dataset name (напр. 'sindrom-dauna') -> dataset_id (UUID)."""
    resp = httpx.get(f"{core_api_url}/ingestion/datasets", headers=_headers(), timeout=15)
    resp.raise_for_status()
    for ds in resp.json().get("datasets", []):
        if ds.get("name") == name:
            return ds["id"]
    raise GarSchemaError(f"датасет {name!r} не найден в GAR")


def fetch_gar_fields(dataset_id: str | None = None, core_api_url: str = DEFAULT_CORE_API_URL) -> dict:
    """Сырой ответ GET /datasets/{id}/metadata-fields."""
    dataset_id = dataset_id or DEFAULT_DATASET_ID or resolve_dataset_id(core_api_url=core_api_url)
    resp = httpx.get(f"{core_api_url}/datasets/{dataset_id}/metadata-fields", headers=_headers(), timeout=15)
    if resp.status_code == 403:
        raise GarSchemaError("403 от GAR API — проверь X-User-ID (нужен admin-* или ACL-правило)")
    resp.raise_for_status()
    return resp.json()


def save_cache(payload: dict, path: Path = _CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache = {"fetched_at": time.time(), "fields": payload}
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cache(path: Path = _CACHE_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_gar_schema(
    *,
    dataset_id: str | None = None,
    force_refresh: bool = False,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    core_api_url: str = DEFAULT_CORE_API_URL,
    path: Path = _CACHE_PATH,
) -> dict:
    """Актуальная схема metadata-fields: из кэша (если не протух) либо
    fetch+пересохранить. При недоступности GAR API — fallback на кэш, даже
    протухший (лучше устаревшие данные, чем падение краулера); если кэша
    вообще нет — исключение."""
    cache = None if force_refresh else load_cache(path)
    if cache and (time.time() - cache.get("fetched_at", 0)) < ttl_seconds:
        return cache["fields"]
    try:
        fields = fetch_gar_fields(dataset_id=dataset_id, core_api_url=core_api_url)
    except (httpx.HTTPError, GarSchemaError) as exc:
        cache = load_cache(path)
        if cache:
            return cache["fields"]
        raise GarSchemaError(f"GAR API недоступен и локальный кэш пуст: {exc}") from exc
    save_cache(fields, path)
    return fields


def field_options(fields: dict, key: str) -> list[str]:
    """Активные value select-поля по его key (напр. 'direction', 'age')."""
    for field in fields.get("fields", []):
        if field["key"] == key and field.get("active", True):
            return [opt["value"] for opt in field.get("options", []) if opt.get("active", True)]
    return []


def category_options_for_direction(fields: dict, direction_value: str) -> list[str]:
    """category — dependent select: его опции привязаны parent_option_id
    к конкретной опции direction, а не к direction напрямую."""
    direction_field = next((f for f in fields.get("fields", []) if f["key"] == "direction"), None)
    category_field = next((f for f in fields.get("fields", []) if f["key"] == "category"), None)
    if not direction_field or not category_field:
        return []
    direction_option = next(
        (o for o in direction_field.get("options", []) if o["value"] == direction_value), None
    )
    if not direction_option:
        return []
    return [
        opt["value"] for opt in category_field.get("options", [])
        if opt.get("active", True) and opt.get("parent_option_id") == direction_option["id"]
    ]


def required_field_keys(fields: dict) -> list[str]:
    return [f["key"] for f in fields.get("fields", []) if f.get("active", True) and f.get("required")]


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Синхронизация схемы metadata-fields из GAR")
    parser.add_argument("--refresh", action="store_true", help="принудительно обновить кэш")
    parser.add_argument("--dataset-id", default=None)
    args = parser.parse_args()

    fields = load_gar_schema(dataset_id=args.dataset_id, force_refresh=args.refresh)
    keys = [f["key"] for f in fields.get("fields", []) if f.get("active", True)]
    print(f"OK: {len(keys)} активных полей: {', '.join(keys)}")
    required = required_field_keys(fields)
    if required:
        print(f"обязательные: {', '.join(required)}")


if __name__ == "__main__":
    _cli()

"""Хранилище реестра источников в GAR с локальным кэшем (ds ADR-0021, #263).

Реестр (лицензия/ToS/publish_permission по домену) живёт в БД GAR
(/source-registry). Чтобы license gate не зависел от доступности GAR,
каждый успешный ответ пишется в data/source_registry_cache.json; при
недоступности GAR читается кэш. Домена нет ни в GAR, ни в кэше — вызывающий
трактует это как pending_manual_review (безопасный дефолт "не скачивать").

Переходный флаг SOURCE_REGISTRY_BACKEND: yaml (по умолчанию, config/licenses.yaml)
или gar. Переключение на gar — после миграции реестра (ds_search#265)."""
from __future__ import annotations

import json
import logging
import os
import tempfile

import yaml
from datetime import datetime, timezone
from pathlib import Path

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient, GarDiscoveryClientError

logger = logging.getLogger(__name__)

_DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "source_registry_cache.json"


def registry_backend() -> str:
    return os.environ.get("SOURCE_REGISTRY_BACKEND", "yaml").strip().lower()


def cache_path() -> Path:
    return Path(os.environ.get("SOURCE_REGISTRY_CACHE") or _DEFAULT_CACHE)


class GarRegistryStore:
    def __init__(self, client=None, cache_file: Path | None = None):
        self._client = client
        self._cache_file = Path(cache_file) if cache_file else cache_path()

    # --- клиент GAR (создаётся лениво, чтобы ошибка конфигурации не ломала импорт) ---
    def _call(self, fn_name: str, *args, **kwargs):
        if self._client is not None:
            return getattr(self._client, fn_name)(*args, **kwargs)
        with GarDiscoveryClient(load_settings()) as client:
            return getattr(client, fn_name)(*args, **kwargs)

    # --- кэш ---
    def _read_cache(self) -> dict[str, dict]:
        try:
            return json.loads(self._cache_file.read_text(encoding="utf-8")).get("entries", {})
        except (OSError, ValueError):
            return {}

    def _write_cache(self, entries: dict[str, dict]) -> None:
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "entries": entries}
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self._cache_file.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, self._cache_file)
        except OSError as exc:
            logger.warning("не удалось записать кэш реестра %s: %s", self._cache_file, exc)

    def _cache_put(self, domain: str, entry: dict | None) -> None:
        entries = self._read_cache()
        if entry is None:
            entries.pop(domain, None)
        else:
            entries[domain] = entry
        self._write_cache(entries)

    # --- API ---
    def load_all(self) -> dict[str, dict]:
        """Весь реестр {domain: entry}. GAR недоступен → кэш (может быть пустым)."""
        try:
            entries = {e["domain"]: e for e in self._call("list_source_registry")}
        except GarDiscoveryClientError as exc:
            logger.warning("реестр GAR недоступен, используется кэш: %s", exc)
            return self._read_cache()
        self._write_cache(entries)
        return entries

    def get(self, domain: str) -> dict | None:
        """Запись по домену. None — нет в реестре ИЛИ GAR недоступен и домена нет в кэше."""
        try:
            entry = self._call("get_source_registry_entry", domain)
        except GarDiscoveryClientError as exc:
            logger.warning("реестр GAR недоступен для %s, используется кэш: %s", domain, exc)
            return self._read_cache().get(domain)
        self._cache_put(domain, entry)
        return entry

    def ensure(self, domain: str, attribution_template: str = "") -> dict | None:
        """Создаёт pending_manual_review, если записи нет. Ошибки не пробрасываются (best effort)."""
        try:
            entry = self._call("ensure_source_registry_entry", domain, attribution_template)
        except GarDiscoveryClientError as exc:
            logger.warning("не удалось создать заготовку реестра для %s: %s", domain, exc)
            return None
        self._cache_put(domain, entry)
        return entry

    def put(self, domain: str, entry: dict) -> dict:
        """Создать/обновить запись (PUT). Ошибки пробрасываются — UI покажет пользователю."""
        saved = self._call("put_source_registry_entry", domain, **entry)
        self._cache_put(domain, saved)
        return saved

    def delete(self, domain: str) -> None:
        self._call("delete_source_registry_entry", domain)
        self._cache_put(domain, None)


# --- фасад для потребителей (UI, скрипты): yaml или GAR по SOURCE_REGISTRY_BACKEND ---
YAML_PATH = Path(__file__).resolve().parents[2] / "config" / "licenses.yaml"
_YAML_HEADER = "# Реестр лицензий/ToS источников (issue #3, ADR-001 п.3).\n"


def _use_gar(path: Path | None) -> bool:
    return (path is None or Path(path) == YAML_PATH) and registry_backend() == "gar"


def load_registry(path: Path | None = None) -> dict[str, dict]:
    if _use_gar(path):
        return GarRegistryStore().load_all()
    p = Path(path) if path else YAML_PATH
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def _yaml_save(registry: dict, p: Path) -> None:
    p.write_text(_YAML_HEADER + yaml.safe_dump(registry, allow_unicode=True, sort_keys=True), encoding="utf-8")


def save_entry(domain: str, entry: dict, path: Path | None = None) -> None:
    if _use_gar(path):
        GarRegistryStore().put(domain, entry)
        return
    p = Path(path) if path else YAML_PATH
    registry = load_registry(p)
    registry[domain] = entry
    _yaml_save(registry, p)


def delete_entry(domain: str, path: Path | None = None) -> None:
    if _use_gar(path):
        GarRegistryStore().delete(domain)
        return
    p = Path(path) if path else YAML_PATH
    registry = load_registry(p)
    registry.pop(domain, None)
    _yaml_save(registry, p)

"""Правка publish_permission домена из отчёта публикации (ds_search#490)."""
from __future__ import annotations

from src.license.checker import PublishPermission
from src.license.registry_store import GarRegistryStore

PUBLISHABLE = {PublishPermission.NOT_REQUIRED.value, PublishPermission.GRANTED.value}


def set_publish_permission(domain: str, value: str, store: GarRegistryStore | None = None) -> dict:
    """Ставит разрешение источнику; нет записи в реестре -> заготовка через ensure. Ошибки пробрасываются."""
    if value not in {p.value for p in PublishPermission}:
        raise ValueError(f"неизвестное разрешение: {value}")
    domain = domain.strip().lower()
    if not domain:
        raise ValueError("пустой домен")
    store = store or GarRegistryStore()
    entry = store.get(domain) or store.ensure(domain) or {"domain": domain}
    entry = {**entry, "publish_permission": value}
    return store.put(domain, entry)

"""Дедупликация находок (issue #18, ADR-002 п.6).

По нормализованному URL против (а) уже загруженных документов локального
корпуса и (б) прошлых находок (approved/rejected/downloaded) из ЛЮБЫХ
прошлых запусков поиска — не только текущего прогона. Проставляет
is_duplicate на кандидатах до upsert в discovered_sources; дубли по
умолчанию скрыты фильтром в UI (issue #19, не в скоупе этой задачи).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..crawler.filters import canonicalize_url
from .config import load_settings
from .gar_client import GarDiscoveryClient

# issue #18: статусы прошлых находок, дублирующие которые не нужно искать заново.
DUPLICATE_STATUSES = ("approved", "rejected", "downloaded")

DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


def loaded_document_urls(data_root: Path = DEFAULT_DATA_ROOT) -> set[str]:
    """Нормализованные URL уже загруженных документов (issue #18 п.а) — из
    JSON-метафайлов локального корпуса data/raw/**/*.json,
    content_status == "saved" (см. src/crawler/crawler.py._save)."""
    urls: set[str] = set()
    if not data_root.exists():
        return urls
    for meta_path in data_root.rglob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("content_status") != "saved":
            continue
        source_url = meta.get("source_url")
        if source_url:
            urls.add(canonicalize_url(source_url))
    return urls


def past_findings_urls(client: GarDiscoveryClient) -> set[str]:
    """Нормализованные URL прошлых находок в статусах approved/rejected/
    downloaded (issue #18 п.б). GET /discovered-sources не скоуплен по
    search_run_id — покрывает все прошлые прогоны, не только текущий."""
    urls: set[str] = set()
    for status in DUPLICATE_STATUSES:
        for row in client.list_discovered_sources(status=status):
            urls.add(canonicalize_url(row["url"]))
    return urls


def mark_duplicates(candidates: list[dict], known_urls: set[str]) -> list[dict]:
    """Проставляет is_duplicate на кандидатах (dict с ключом 'url') перед
    upsert в discovered_sources."""
    result = []
    for item in candidates:
        item = dict(item)
        item["is_duplicate"] = canonicalize_url(item["url"]) in known_urls
        result.append(item)
    return result


def dedup_candidates(
    candidates: list[dict],
    data_root: Path = DEFAULT_DATA_ROOT,
    client: GarDiscoveryClient | None = None,
) -> list[dict]:
    """Полный дедуп-проход перед upsert: собирает known_urls из локального
    корпуса и прошлых находок, помечает кандидатов is_duplicate.
    Кандидаты — dict-и, готовые стать DiscoveredSourceCreate
    (url/title/snippet/domain/...)."""
    known = loaded_document_urls(data_root)
    if client is not None:
        known |= past_findings_urls(client)
    else:
        with GarDiscoveryClient(load_settings()) as c:
            known |= past_findings_urls(c)
    return mark_duplicates(candidates, known)

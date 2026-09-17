"""RSS-адаптер автосбора новостей (issue #157, эпик #156, ADR-010).

Fetch-only слой: parse фида -> list[RssHit]. Даунстрим (dedup, license-гейт,
download, LLM-draft, insert в news_items) переиспользует _collect_one из
collect.py (см. collect_rss там же) — RSS не дублирует эту логику.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import yaml

logger = logging.getLogger(__name__)

SOURCES_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "rss_sources.yaml"


@dataclass
class RssHit:
    url: str
    title: str
    source_name: str
    published_at: datetime | None


def load_sources_config(path: Path = SOURCES_CONFIG_PATH) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("sources") or []


def _parse_published(entry) -> datetime | None:
    """feedparser отдаёт published_parsed/updated_parsed как
    time.struct_time в UTC (сам приводит любые TZ фида к UTC)."""
    for key in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, key, None)
        if struct:
            return datetime(*struct[:6], tzinfo=timezone.utc)
    return None


def fetch_feed(source: dict, max_age_days: int | None = 5) -> list[RssHit]:
    """Парсит один RSS/Atom-фид. max_age_days=None — без фильтра свежести
    (issue #159: ручной запуск за период N дней передаёт сюда N вместо 5,
    отдельного режима нет — см. ADR-010)."""
    name = source["name"]
    feed_url = source["url"]
    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        logger.warning(
            "rss %s (%s) не распарсен: %s", name, feed_url, parsed.get("bozo_exception"),
        )
        return []

    cutoff = None
    if max_age_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    hits: list[RssHit] = []
    for entry in parsed.entries:
        url = entry.get("link")
        if not url:
            continue
        published_at = _parse_published(entry)
        if cutoff is not None and published_at is not None and published_at < cutoff:
            continue  # issue #158: фильтр свежести
        # Записи без даты публикации не отбрасываем (некоторые фиды её не
        # отдают) — дедуп по source_url в news.db всё равно защищает от
        # повторной обработки при следующих прогонах.
        hits.append(
            RssHit(url=url, title=entry.get("title", ""), source_name=name, published_at=published_at)
        )
    return hits


def fetch_all(sources: list[dict] | None = None, max_age_days: int | None = 5) -> list[RssHit]:
    sources = sources if sources is not None else load_sources_config()
    all_hits: list[RssHit] = []
    for source in sources:
        try:
            all_hits.extend(fetch_feed(source, max_age_days=max_age_days))
        except Exception as exc:  # noqa: BLE001 — один сбойный фид не должен ронять весь прогон
            logger.warning("фид %s упал: %s", source.get("name"), exc)
    return all_hits

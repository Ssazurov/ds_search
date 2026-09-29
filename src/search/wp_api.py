"""Поиск по сайту через WordPress REST API (wp-json/wp/v2/posts).

Даёт точные даты публикации и серверный фильтр периода - в отличие от
веб-поисковиков. Если у домена нет открытого WP API, возвращает None, и
вызывающий код переходит на обычную цепочку провайдеров."""
from __future__ import annotations

import html
import re
from datetime import datetime

import httpx

from .base import SearchHit
from .dates import parse_published

_TAG_RE = re.compile(r"<[^>]+>")
_UA = {"User-Agent": "Mozilla/5.0 (ds_search)"}


def _clean(text: str | None) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def wp_search(
    domain: str, query: str, max_results: int = 10,
    date_from: datetime | None = None, date_to: datetime | None = None,
    timeout: float = 15.0,
) -> list[SearchHit] | None:
    """None - WP API недоступен (не WordPress/закрыт/ошибка); [] - API работает, ничего нет."""
    params: dict = {
        "search": query, "per_page": min(100, max(1, max_results)),
        "orderby": "date", "order": "desc",
        "_fields": "link,date_gmt,date,title,excerpt",
    }
    if date_from:
        params["after"] = date_from.strftime("%Y-%m-%dT%H:%M:%S")
    if date_to:
        params["before"] = date_to.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        resp = httpx.get(f"https://{domain}/wp-json/wp/v2/posts", params=params,
                         headers=_UA, follow_redirects=True, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:  # noqa: BLE001 - недоступен/не JSON -> фолбэк
        return None
    if not isinstance(data, list):
        return None
    hits = []
    for it in data:
        if not isinstance(it, dict) or not it.get("link"):
            continue
        hits.append(SearchHit(
            url=it["link"],
            title=_clean((it.get("title") or {}).get("rendered")),
            snippet=_clean((it.get("excerpt") or {}).get("rendered")),
            published_at=parse_published(it.get("date_gmt") or it.get("date")),
        ))
    return hits

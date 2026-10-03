"""Поиск постов по всей VK через newsfeed.search (issue #463, epic #465).

Дополняет обычную цепочку провайдеров: это не fallback (как wp/rss/sitemap
для конкретного домена), а отдельный источник, который всегда ищет по всей
VK, если задан VK_USER_TOKEN. Без токена — тихо отключён (None), чтобы не
ломать поиск для окружений без VK."""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

from .base import SearchHit
from .vk_client import VkAuthError, VkClient

logger = logging.getLogger(__name__)

_TITLE_MAX = 80
_SNIPPET_MAX = 300
_WS_RE = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    return _WS_RE.sub(" ", html.unescape(text or "")).strip()


def _post_url(owner_id: int, post_id: int) -> str:
    return f"https://vk.ru/wall{owner_id}_{post_id}"


def _to_hit(item: dict) -> SearchHit | None:
    owner_id = item.get("owner_id")
    post_id = item.get("id")
    if owner_id is None or post_id is None:
        return None
    text = _clean(item.get("text"))
    if not text:
        return None  # пост без текста (репост картинки и т.п.) - неинформативен для поиска
    title = text if len(text) <= _TITLE_MAX else text[:_TITLE_MAX - 1].rstrip() + "…"
    snippet = text if len(text) <= _SNIPPET_MAX else text[:_SNIPPET_MAX - 1].rstrip() + "…"
    published_at = None
    ts = item.get("date")
    if ts:
        try:
            published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OSError):
            published_at = None
    return SearchHit(url=_post_url(owner_id, post_id), title=title, snippet=snippet, published_at=published_at)


_NUM_RE = re.compile(r"^-?\d+$")
_COMMUNITY_RE = re.compile(r"^(?:club|public)(\d+)$")
_USER_ID_RE = re.compile(r"^id(\d+)$")


def parse_vk_community(raw: str) -> dict | None:
    """'https://vk.com/club216520775', 'vk.ru/public123', 'club1', '-1', 'screen_name'
    -> {'owner_id': -N} (сообщество) | {'domain': 'screen_name'}; None — пусто/не разобрано."""
    s = (raw or "").strip()
    s = re.sub(r"^https?://", "", s).removeprefix("www.")
    s = re.sub(r"^(vk\.com|vk\.ru)/", "", s).split("?")[0].split("#")[0].strip("/ ")
    if not s:
        return None
    if _NUM_RE.match(s):
        return {"owner_id": int(s) if s.startswith("-") else -int(s)}
    if m := _COMMUNITY_RE.match(s):
        return {"owner_id": -int(m.group(1))}
    if m := _USER_ID_RE.match(s):
        return {"owner_id": int(m.group(1))}
    if re.match(r"^[A-Za-z0-9_.]{2,}$", s):
        return {"domain": s}
    return None


def vk_community_search(
    query: str, community: str, max_results: int = 10,
    date_from: datetime | None = None, date_to: datetime | None = None,
    client: VkClient | None = None,
) -> list[SearchHit] | None:
    """Посты только из одного сообщества VK через wall.search (issue #464).
    None — токен не задан / VK API недоступен / сообщество не разобрано;
    [] — токен есть, находок нет."""
    target = parse_vk_community(community)
    if target is None:
        return None
    client = client or VkClient()
    if not client.token:
        return None
    try:
        resp = client.wall_search(query, count=min(max(max_results, 1), 100), **target)
    except VkAuthError as exc:
        logger.warning("VK wall.search недоступен: %s", exc)
        return None
    except Exception:  # noqa: BLE001
        logger.exception("VK wall.search: неожиданная ошибка")
        return None
    hits: list[SearchHit] = []
    for item in resp.get("items", []):
        hit = _to_hit(item)
        if not hit or hit.published_at is None and (date_from or date_to):
            continue
        if date_from and hit.published_at < date_from:
            continue
        if date_to and hit.published_at > date_to:
            continue
        hits.append(hit)
    return hits[:max_results]


def vk_search(
    query: str, max_results: int = 10,
    date_from: datetime | None = None, date_to: datetime | None = None,
    client: VkClient | None = None,
) -> list[SearchHit] | None:
    """Посты по теме во всей VK (issue #463). date_from/date_to применяются
    на вызывающей стороне (newsfeed.search фильтр по периоду ненадёжен).
    None — VK_USER_TOKEN не задан или VK API недоступен; [] — токен есть,
    находок нет."""
    client = client or VkClient()
    if not client.token:
        return None
    try:
        resp = client.newsfeed_search(query, count=min(max(max_results, 1), 200))
    except VkAuthError as exc:
        logger.warning("VK newsfeed.search недоступен: %s", exc)
        return None
    except Exception:  # noqa: BLE001 — доп. источник, не должен ронять весь поиск
        logger.exception("VK newsfeed.search: неожиданная ошибка")
        return None
    hits: list[SearchHit] = []
    for item in resp.get("items", []):
        hit = _to_hit(item)
        if not hit or hit.published_at is None and (date_from or date_to):
            continue
        if date_from and hit.published_at < date_from:
            continue
        if date_to and hit.published_at > date_to:
            continue
        hits.append(hit)
    return hits[:max_results]

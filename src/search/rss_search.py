"""Поиск по сайту через RSS/Atom фиды (issue #382).

Автообнаружение фида через <link rel="alternate"> и стандартные пути
(/feed, /rss, /rss.xml). Фильтр по запросу (заголовок/описание) и периоду
(pubDate). Если фид недоступен, возвращает None для fallback на следующий адаптер."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from html.parser import HTMLParser

import feedparser
import httpx

from .base import SearchHit
from .dates import parse_published

logger = logging.getLogger(__name__)

_UA = {"User-Agent": "Mozilla/5.0 (ds_search)"}
_FEED_PATHS = ["/feed", "/rss", "/rss.xml", "/atom.xml", "/feed.xml"]


class _LinkParser(HTMLParser):
    """Ищет <link rel="alternate" type="application/rss+xml|atom+xml" href="...">."""
    def __init__(self):
        super().__init__()
        self.feed_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        attr_d = dict(attrs)
        rel = (attr_d.get("rel") or "").lower()
        typ = (attr_d.get("type") or "").lower()
        href = attr_d.get("href")
        if "alternate" in rel and ("rss" in typ or "atom" in typ) and href:
            self.feed_urls.append(href)


def _discover_feed(domain: str, timeout: float = 15.0) -> str | None:
    """Ищет RSS/Atom через <link> на главной, затем пробует стандартные пути.
    Возвращает первый найденный URL или None."""
    try:
        resp = httpx.get(f"https://{domain}", headers=_UA, follow_redirects=True, timeout=timeout)
        if resp.status_code == 200:
            parser = _LinkParser()
            parser.feed(resp.text[:100_000])  # парсим только начало
            if parser.feed_urls:
                # относительный URL -> абсолютный
                url = parser.feed_urls[0]
                if url.startswith("//"):
                    return "https:" + url
                if url.startswith("/"):
                    return f"https://{domain}{url}"
                if url.startswith("http"):
                    return url
                return f"https://{domain}/{url}"
    except Exception:  # noqa: BLE001
        logger.debug("feed discovery failed for %s", domain, exc_info=True)

    # пробуем стандартные пути
    for path in _FEED_PATHS:
        try:
            test_url = f"https://{domain}{path}"
            resp = httpx.head(test_url, headers=_UA, follow_redirects=True, timeout=5.0)
            if resp.status_code == 200:
                return test_url
        except Exception:  # noqa: BLE001
            continue
    return None


def _clean_html(text: str | None) -> str:
    """Убирает HTML-теги из текста."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _matches_query(title: str, description: str, query: str) -> bool:
    """Проверяет, содержит ли title или description слова из query (case-insensitive)."""
    text = (title + " " + description).lower()
    # разбиваем query на токены и проверяем, что все есть в тексте
    tokens = [t.strip() for t in query.lower().split() if t.strip()]
    return all(tok in text for tok in tokens)


def rss_search(
    domain: str, query: str, max_results: int = 10,
    date_from: datetime | None = None, date_to: datetime | None = None,
    timeout: float = 15.0,
) -> list[SearchHit] | None:
    """None - RSS недоступен; [] - RSS работает, но ничего не нашлось."""
    feed_url = _discover_feed(domain, timeout)
    if not feed_url:
        return None

    try:
        # feedparser сам обрабатывает timeout через urllib
        parsed = feedparser.parse(feed_url)
        if parsed.bozo and not parsed.entries:
            logger.debug("rss parse failed for %s: %s", domain, parsed.get("bozo_exception"))
            return None
    except Exception:  # noqa: BLE001
        logger.debug("rss fetch failed for %s", domain, exc_info=True)
        return None

    hits: list[SearchHit] = []
    for entry in parsed.entries:
        url = entry.get("link")
        if not url:
            continue

        # parse published date
        published_at = None
        for key in ("published_parsed", "updated_parsed"):
            struct = getattr(entry, key, None)
            if struct:
                from datetime import timezone
                published_at = datetime(*struct[:6], tzinfo=timezone.utc)
                break

        # фильтр по периоду
        if date_from or date_to:
            if published_at is None:
                continue  # без даты не можем проверить период
            pub_naive = published_at.replace(tzinfo=None)
            if date_from and pub_naive < date_from.replace(tzinfo=None):
                continue
            if date_to and pub_naive > date_to.replace(tzinfo=None):
                continue

        # фильтр по запросу
        title = _clean_html(entry.get("title", ""))
        description = _clean_html(entry.get("summary") or entry.get("description", ""))
        if not _matches_query(title, description, query):
            continue

        hits.append(SearchHit(
            url=url,
            title=title,
            snippet=description[:300] if description else "",
            published_at=published_at,
        ))

        if len(hits) >= max_results:
            break

    return hits

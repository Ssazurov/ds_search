"""Поиск по сайту через sitemap.xml (issue #382).

Ищет /sitemap.xml и robots.txt, извлекает URL с <lastmod> в заданном периоде.
lastmod не равен дате публикации -> требуется подтверждение через _fetch_published.
Если sitemap недоступен, возвращает None для fallback на следующий адаптер."""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx

from .base import SearchHit
from .dates import parse_published

logger = logging.getLogger(__name__)

_UA = {"User-Agent": "Mozilla/5.0 (ds_search)"}


def _discover_sitemap(domain: str, timeout: float = 15.0) -> list[str]:
    """Ищет sitemap через /sitemap.xml и robots.txt. Возвращает список URL."""
    urls: list[str] = []
    
    # пробуем прямой путь
    try:
        resp = httpx.get(f"https://{domain}/sitemap.xml", headers=_UA, 
                        follow_redirects=True, timeout=timeout)
        if resp.status_code == 200:
            urls.append(f"https://{domain}/sitemap.xml")
    except Exception:  # noqa: BLE001
        pass

    # пробуем robots.txt
    try:
        resp = httpx.get(f"https://{domain}/robots.txt", headers=_UA,
                        follow_redirects=True, timeout=timeout)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url not in urls:
                        urls.append(sitemap_url)
    except Exception:  # noqa: BLE001
        pass

    return urls


def _parse_sitemap(url: str, timeout: float = 15.0) -> list[tuple[str, datetime | None]]:
    """Парсит один sitemap, возвращает [(url, lastmod), ...]."""
    try:
        resp = httpx.get(url, headers=_UA, follow_redirects=True, timeout=timeout)
        if resp.status_code != 200:
            return []
        
        root = ET.fromstring(resp.content)
        # namespace может быть разным
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        
        results: list[tuple[str, datetime | None]] = []
        
        # проверяем, это sitemap index или обычный sitemap
        for sitemap_elem in root.findall(".//sm:sitemap", ns):
            loc = sitemap_elem.find("sm:loc", ns)
            if loc is not None and loc.text:
                # рекурсивно парсим вложенный sitemap
                results.extend(_parse_sitemap(loc.text, timeout))
        
        # парсим URL-ы
        for url_elem in root.findall(".//sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            if loc is None or not loc.text:
                continue
            
            lastmod_elem = url_elem.find("sm:lastmod", ns)
            lastmod = None
            if lastmod_elem is not None and lastmod_elem.text:
                lastmod = parse_published(lastmod_elem.text)
            
            results.append((loc.text, lastmod))
        
        return results
    except Exception:  # noqa: BLE001
        logger.debug("sitemap parse failed for %s", url, exc_info=True)
        return []


_LD_DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_ITEMPROP_RE = re.compile(
    r'itemprop=["\']datePublished["\'][^>]*?(?:content|datetime)=["\']([^"\']+)["\']', re.IGNORECASE
)


def _fetch_published_and_content(url: str, query: str, timeout: float = 8.0) -> tuple[datetime | None, str, str]:
    """Извлекает дату публикации, title и snippet со страницы.
    Возвращает (published_at, title, snippet)."""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=timeout, headers=_UA)
        resp.raise_for_status()
        html = resp.text
        
        # дата публикации
        from ..metadata.meta_extract import extract_meta_tags
        meta = extract_meta_tags(html)
        published_at = None
        for raw in (meta.get("article:published_time"), meta.get("og:published_time")):
            d = parse_published(raw)
            if d:
                published_at = d
                break
        
        if not published_at:
            for rx in (_LD_DATE_RE, _ITEMPROP_RE):
                m = rx.search(html)
                if m:
                    d = parse_published(m.group(1))
                    if d:
                        published_at = d
                        break
        
        # title и snippet
        title = meta.get("og:title") or meta.get("title", "")
        snippet = meta.get("og:description") or meta.get("description", "")
        
        # проверяем совпадение с query (в title, snippet или body)
        text = (title + " " + snippet + " " + html).lower()
        tokens = [t.strip() for t in query.lower().split() if t.strip()]
        matches = all(tok in text for tok in tokens)
        
        return (published_at, title, snippet) if matches else (None, "", "")
        
    except Exception:  # noqa: BLE001
        logger.debug("fetch failed for %s", url, exc_info=True)
        return (None, "", "")


def sitemap_search(
    domain: str, query: str, max_results: int = 10,
    date_from: datetime | None = None, date_to: datetime | None = None,
    timeout: float = 15.0,
) -> list[SearchHit] | None:
    """None - sitemap недоступен; [] - sitemap работает, но ничего не нашлось."""
    sitemap_urls = _discover_sitemap(domain, timeout)
    if not sitemap_urls:
        return None

    # собираем все URL из всех sitemap-ов
    all_entries: list[tuple[str, datetime | None]] = []
    for sitemap_url in sitemap_urls:
        all_entries.extend(_parse_sitemap(sitemap_url, timeout))
    
    if not all_entries:
        return []

    # фильтруем по периоду lastmod (если указан)
    candidates: list[tuple[str, datetime | None]] = []
    for url, lastmod in all_entries:
        if date_from or date_to:
            if lastmod is None:
                continue
            lm_naive = lastmod.replace(tzinfo=None)
            if date_from and lm_naive < date_from.replace(tzinfo=None):
                continue
            if date_to and lm_naive > date_to.replace(tzinfo=None):
                continue
        candidates.append((url, lastmod))

    # ограничиваем количество для загрузки
    candidates = candidates[:min(100, max_results * 3)]

    # загружаем страницы параллельно для уточнения даты и проверки query
    hits: list[SearchHit] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = ex.map(
            lambda entry: _fetch_published_and_content(entry[0], query, timeout=8.0),
            candidates
        )
        
        for (url, lastmod), (published_at, title, snippet) in zip(candidates, results):
            if not title:  # не прошло фильтр по query
                continue
            
            # используем published_at из страницы, если есть, иначе None
            hits.append(SearchHit(
                url=url,
                title=title,
                snippet=snippet[:300] if snippet else "",
                published_at=published_at,  # может быть None
            ))
            
            if len(hits) >= max_results:
                break

    return hits

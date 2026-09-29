"""Запуск поиска -> запись находок в discovered_sources (issue #19, часть
"Параметры поиска"). Связывает уже готовые кирпичи: search_provider
(issue #15), discovery REST API (gar-core-api#221), дедуп (issue #18).

Это первый код, который реально создаёт discovered_sources из результатов
поиска — раньше существовали только probe (issue #17) и dedup над уже
существующими находками.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlsplit

import httpx

from ..crawler.filters import canonicalize_url
from ..search.base import QuotaExceeded, SearchHit
from ..metadata.meta_extract import extract_meta_tags
from ..search.chain import SearchProviderChain
from ..search.dates import parse_published
from .classify import classify
from .config import Settings, load_settings
from .dedup import dedup_candidates
from .gar_client import GarDiscoveryClient

logger = logging.getLogger(__name__)


def _hit_to_candidate(hit: SearchHit, metadata: dict | None = None) -> dict:
    domain = urlsplit(hit.url).netloc.lower()
    candidate = {
        "url": canonicalize_url(hit.url),
        "domain": domain,
        "title": hit.title,
        "snippet": hit.snippet,
    }
    # issue #21: keyword-эвристика по title+snippet заполняет suggested_*
    # черновым значением (или None, если нет уверенного совпадения).
    candidate.update(classify(hit.title, hit.snippet))
    # #355: дата публикации из ответа провайдера; ключ не добавляем, если её нет
    if getattr(hit, "published_at", None):
        candidate["source_published_at"] = hit.published_at.isoformat()
    if metadata:
        # issue #19 п.2: явные direction/category/... из параметров поиска
        # приоритетнее эвристики issue #21 -> suggested_* поля
        # discovered_sources (gar-core-api PR #222).
        candidate.update({k: v for k, v in metadata.items() if v})
    return candidate


def normalize_domains(raw: str | list[str] | None) -> list[str]:
    """Разбирает список доменов (строка через запятую/пробел/перенос или
    список) -> ['example.org', ...]: без схемы, пути, www, в нижнем регистре,
    без дублей. Никаких проверок разрешений публикации."""
    if not raw:
        return []
    items = re.split(r"[\s,;]+", raw) if isinstance(raw, str) else list(raw)
    result: list[str] = []
    for item in items:
        item = item.strip().lower()
        if not item:
            continue
        host = urlsplit(item if "//" in item else f"//{item}").netloc
        host = host.split("@")[-1].split(":")[0].removeprefix("www.")
        if "." in host and host not in result:  # "и", "or" и т.п. — не домены
            result.append(host)
    return result


def _in_domains(url: str, domains: list[str]) -> bool:
    host = urlsplit(url).netloc.lower().split(":")[0].removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in domains)


def _search(chain: SearchProviderChain, query: str, doms: list[str], max_results: int,
            date_from: datetime | None = None, date_to: datetime | None = None) -> list[SearchHit]:
    """Без доменов — обычный поиск. С доменами — отдельный запрос
    `query site:домен` на каждый (один OR-запрос провайдеры выполняют
    ненадёжно), результаты фильтруются по хосту, объединяются без дублей
    и делятся между доменами поровну (не больше max_results в сумме)."""
    dates = {k: v for k, v in (("date_from", date_from), ("date_to", date_to)) if v}
    if not doms:
        return chain.search(query, max_results=max_results, **dates)
    per_domain = -(-max_results // len(doms))
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for d in doms:
        found = chain.search(f"{query} site:{d}", max_results=min(100, per_domain * 2), **dates)
        taken = 0
        for h in found:
            if taken >= per_domain:
                break
            if _in_domains(h.url, [d]) and h.url not in seen:
                seen.add(h.url)
                hits.append(h)
                taken += 1
    return hits[:max_results]


_LD_DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_ITEMPROP_RE = re.compile(
    r'itemprop=["\']datePublished["\'][^>]*?(?:content|datetime)=["\']([^"\']+)["\']', re.IGNORECASE
)


def _fetch_published(url: str, timeout: float = 8.0) -> datetime | None:
    """Достаёт дату публикации со страницы: og/article meta, JSON-LD, itemprop.
    Только published (не modified). Любая ошибка -> None."""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0 (ds_search)"})
        resp.raise_for_status()
        html = resp.text
        meta = extract_meta_tags(html)
        for raw in (meta.get("article:published_time"), meta.get("og:published_time")):
            d = parse_published(raw)
            if d:
                return d
        for rx in (_LD_DATE_RE, _ITEMPROP_RE):
            m = rx.search(html)
            if m:
                d = parse_published(m.group(1))
                if d:
                    return d
    except Exception:  # noqa: BLE001 — обогащение best-effort
        logger.debug("date fetch failed: %s", url, exc_info=True)
    return None


def _enrich_dates(hits: list[SearchHit], date_from: datetime | None,
                  date_to: datetime | None) -> None:
    """Для находок без published_at при заданном периоде добирает дату со страницы."""
    if not (date_from or date_to):
        return
    todo = [h for h in hits if h.published_at is None]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=8) as ex:
        for h, d in zip(todo, ex.map(lambda x: _fetch_published(x.url), todo)):
            if d:
                h.published_at = d


def _filter_by_period(hits: list[SearchHit], date_from: datetime | None,
                      date_to: datetime | None) -> list[SearchHit]:
    """Провайдеры фильтруют период ненадёжно: отбрасываем находки, у которых
    известная published_at вне [date_from, date_to]. Без даты — оставляем."""
    if not (date_from or date_to):
        return hits

    def ok(h: SearchHit) -> bool:
        d = h.published_at
        if d is None:
            return True
        d = d.replace(tzinfo=None)
        if date_from and d < date_from.replace(tzinfo=None):
            return False
        if date_to and d > date_to.replace(tzinfo=None):
            return False
        return True

    return [h for h in hits if ok(h)]


def run_search(
    query: str,
    chain: SearchProviderChain,
    max_results: int = 10,
    settings: Settings | None = None,
    metadata: dict | None = None,
    domains: str | list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Выполняет поиск, дедуплицирует находки и upsert-ит их в
    discovered_sources под новым search_run. `metadata` — необязательные
    suggested_direction/suggested_category/suggested_doc_type/
    suggested_target_audience из параметров поиска (issue #19 п.2),
    проставляются на все находки этого запуска. Возвращает
    {"run_id", "status", "result_count", "found", "duplicates", "new",
    "with_date", "provider", "error"}."""
    settings = settings or load_settings()
    doms = normalize_domains(domains)
    with GarDiscoveryClient(settings) as client:
        run = client.create_search_run(query=query, provider=chain.providers[0].name)
        run_id = run["id"]
        provider_name = chain.providers[0].name
        try:
            hits = _search(chain, query, doms, max_results, date_from, date_to)
            _enrich_dates(hits, date_from, date_to)
            hits = _filter_by_period(hits, date_from, date_to)
        except QuotaExceeded as exc:
            logger.warning("search run %s failed: %s", run_id, exc)
            client.update_search_run(run_id, status="failed", error=str(exc))
            return {
                "run_id": run_id,
                "status": "failed",
                "result_count": 0,
                "found": 0,
                "duplicates": 0,
                "new": 0,
                "with_date": 0,
                "provider": provider_name,
                "error": str(exc),
            }
        except Exception as exc:
            logger.exception("search run %s failed", run_id)
            client.update_search_run(run_id, status="failed", error=str(exc))
            return {
                "run_id": run_id,
                "status": "failed",
                "result_count": 0,
                "found": 0,
                "duplicates": 0,
                "new": 0,
                "with_date": 0,
                "provider": provider_name,
                "error": str(exc),
            }

        candidates = [_hit_to_candidate(h, metadata) for h in hits]
        found = len(candidates)
        candidates = dedup_candidates(candidates, client=client)
        duplicates = sum(1 for c in candidates if c.get("is_duplicate"))
        new = found - duplicates
        with_date = sum(1 for c in candidates if "source_published_at" in c)

        if candidates:
            client.upsert_discovered_sources(run_id, candidates)
        client.update_search_run(run_id, status="completed", result_count=len(candidates))
        logger.info("search run %s: %d находок (query=%r)", run_id, len(candidates), query)
        return {
            "run_id": run_id,
            "status": "completed",
            "result_count": len(candidates),
            "found": found,
            "duplicates": duplicates,
            "new": new,
            "with_date": with_date,
            "provider": provider_name,
            "error": None,
        }

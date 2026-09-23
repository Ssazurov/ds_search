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
from datetime import datetime
from urllib.parse import urlsplit

from ..crawler.filters import canonicalize_url
from ..search.base import QuotaExceeded, SearchHit
from ..search.chain import SearchProviderChain
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
    {"run_id", "status", "result_count"}."""
    settings = settings or load_settings()
    doms = normalize_domains(domains)
    with GarDiscoveryClient(settings) as client:
        run = client.create_search_run(query=query, provider=chain.providers[0].name)
        run_id = run["id"]
        try:
            hits = _search(chain, query, doms, max_results, date_from, date_to)
        except QuotaExceeded as exc:
            logger.warning("search run %s failed: %s", run_id, exc)
            client.update_search_run(run_id, status="failed", error=str(exc))
            return {"run_id": run_id, "status": "failed", "result_count": 0}

        candidates = [_hit_to_candidate(h, metadata) for h in hits]
        candidates = dedup_candidates(candidates, client=client)
        if candidates:
            client.upsert_discovered_sources(run_id, candidates)
        client.update_search_run(run_id, status="completed", result_count=len(candidates))
        logger.info("search run %s: %d находок (query=%r)", run_id, len(candidates), query)
        return {"run_id": run_id, "status": "completed", "result_count": len(candidates)}

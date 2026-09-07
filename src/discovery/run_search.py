"""Запуск поиска -> запись находок в discovered_sources (issue #19, часть
"Параметры поиска"). Связывает уже готовые кирпичи: search_provider
(issue #15), discovery REST API (gar-core-api#221), дедуп (issue #18).

Это первый код, который реально создаёт discovered_sources из результатов
поиска — раньше существовали только probe (issue #17) и dedup над уже
существующими находками.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from ..crawler.filters import canonicalize_url
from ..search.base import QuotaExceeded, SearchHit
from ..search.chain import SearchProviderChain
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
    if metadata:
        # issue #19 п.2: direction/category/target_audience из параметров
        # поиска -> suggested_* поля discovered_sources (gar-core-api PR #222).
        candidate.update({k: v for k, v in metadata.items() if v})
    return candidate


def run_search(
    query: str,
    chain: SearchProviderChain,
    max_results: int = 10,
    settings: Settings | None = None,
    metadata: dict | None = None,
) -> dict:
    """Выполняет поиск, дедуплицирует находки и upsert-ит их в
    discovered_sources под новым search_run. `metadata` — необязательные
    suggested_direction/suggested_category/suggested_doc_type/
    suggested_target_audience из параметров поиска (issue #19 п.2),
    проставляются на все находки этого запуска. Возвращает
    {"run_id", "status", "result_count"}."""
    settings = settings or load_settings()
    with GarDiscoveryClient(settings) as client:
        run = client.create_search_run(query=query, provider=chain.providers[0].name)
        run_id = run["id"]
        try:
            hits = chain.search(query, max_results=max_results)
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

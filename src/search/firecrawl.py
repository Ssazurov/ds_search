"""Firecrawl provider (issue #178, дополнение к ADR-011). Free tier:
1000 кредитов/мес, без карты; поиск = 2 кредита за пачку до 10
результатов.

Проверено 2026-09-17: api.tavily.com не отвечает из рабочей сети
(TLS проходит, HTTP-ответа нет), Brave снял бесплатный тир (нужна
карта) — api.firecrawl.dev отвечает штатно. API-ключ — FIRECRAWL_API_KEY.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import httpx

from .base import QuotaExceeded, SearchHit, SearchProvider
from .quota import QuotaState

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/search"
DEFAULT_QUOTA_PATH = Path("data/search_quota.json")
FREE_TIER_MONTHLY_CREDITS = 1000
CREDITS_PER_SEARCH = 2  # до 10 результатов за пачку


class FirecrawlProvider(SearchProvider):
    name = "firecrawl"

    def __init__(
        self,
        api_key: str | None = None,
        quota_path: Path = DEFAULT_QUOTA_PATH,
        monthly_limit: int = FREE_TIER_MONTHLY_CREDITS,
    ) -> None:
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        self.quota = QuotaState(
            path=quota_path, provider=self.name, limit=monthly_limit, period="monthly"
        )

    def search(
        self, query: str, max_results: int = 10,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> list[SearchHit]:
        if not query.strip():
            raise ValueError("Поисковый запрос не должен быть пустым")
        if not 1 <= max_results <= 100:
            raise ValueError("max_results должен быть от 1 до 100")
        if not self.api_key:
            raise QuotaExceeded(f"{self.name}: нет FIRECRAWL_API_KEY")
        if not self.quota.has_quota(cost=CREDITS_PER_SEARCH):
            raise QuotaExceeded(f"{self.name}: месячная квота исчерпана")
        payload = {"query": query, "limit": max_results}
        if date_from or date_to:
            fmt = lambda d: d.strftime("%m/%d/%Y") if d else ""  # noqa: E731
            payload["tbs"] = f"cdr:1,cd_min:{fmt(date_from)},cd_max:{fmt(date_to)}"
        resp = httpx.post(
            FIRECRAWL_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=20.0,
        )
        if resp.status_code in (402, 429):
            raise QuotaExceeded(f"{self.name}: API сообщил об исчерпании квоты")
        resp.raise_for_status()
        data = resp.json()
        self.quota.record(cost=CREDITS_PER_SEARCH)
        return [
            SearchHit(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("description", ""),
            )
            for item in data.get("data", [])
        ]

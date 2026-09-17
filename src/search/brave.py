"""Brave Search provider (issue #171, ADR-011). Free tier: 2000 запросов/мес.

API-ключ — BRAVE_API_KEY. Доки: https://api.search.brave.com/app/documentation
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from .base import QuotaExceeded, SearchHit, SearchProvider
from .quota import QuotaState

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_QUOTA_PATH = Path("data/search_quota.json")
FREE_TIER_MONTHLY_CREDITS = 2000


class BraveProvider(SearchProvider):
    name = "brave"

    def __init__(
        self,
        api_key: str | None = None,
        quota_path: Path = DEFAULT_QUOTA_PATH,
        monthly_limit: int = FREE_TIER_MONTHLY_CREDITS,
    ) -> None:
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY")
        self.quota = QuotaState(
            path=quota_path, provider=self.name, limit=monthly_limit, period="monthly"
        )

    def search(self, query: str, max_results: int = 10) -> list[SearchHit]:
        if not query.strip():
            raise ValueError("Поисковый запрос не должен быть пустым")
        if not 1 <= max_results <= 100:
            raise ValueError("max_results должен быть от 1 до 100")
        if not self.api_key:
            raise QuotaExceeded(f"{self.name}: BRAVE_API_KEY не задан")
        if not self.quota.has_quota(cost=1):
            raise QuotaExceeded(f"{self.name}: месячная квота исчерпана")
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params = {"q": query, "count": min(max_results, 20)}
        resp = httpx.get(BRAVE_API_URL, params=params, headers=headers, timeout=15.0)
        if resp.status_code in (401, 429):
            raise QuotaExceeded(f"{self.name}: API сообщил об исчерпании квоты")
        resp.raise_for_status()
        data = resp.json()
        self.quota.record(cost=1)
        results = data.get("web", {}).get("results", [])
        return [
            SearchHit(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("description", ""),
            )
            for item in results[:max_results]
        ]

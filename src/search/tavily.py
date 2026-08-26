"""Tavily provider (issue #15). Free tier: 1000 кредитов/мес, без карты.

Проверено 2026-08-26 (см. ADR-002, "Уточнения"). API-ключ — TAVILY_API_KEY.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from .base import QuotaExceeded, SearchHit, SearchProvider
from .quota import QuotaState

TAVILY_API_URL = "https://api.tavily.com/search"
DEFAULT_QUOTA_PATH = Path("data/search_quota.json")
FREE_TIER_MONTHLY_CREDITS = 1000


class TavilyProvider(SearchProvider):
    name = "tavily"

    def __init__(
        self,
        api_key: str | None = None,
        quota_path: Path = DEFAULT_QUOTA_PATH,
        monthly_limit: int = FREE_TIER_MONTHLY_CREDITS,
    ) -> None:
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY не задан")
        self.quota = QuotaState(
            path=quota_path, provider=self.name, limit=monthly_limit, period="monthly"
        )

    def search(self, query: str, max_results: int = 10) -> list[SearchHit]:
        if not query.strip():
            raise ValueError("Поисковый запрос не должен быть пустым")
        if not 1 <= max_results <= 100:
            raise ValueError("max_results должен быть от 1 до 100")
        if not self.quota.has_quota(cost=1):
            raise QuotaExceeded(f"{self.name}: месячная квота исчерпана")
        resp = httpx.post(
            TAVILY_API_URL,
            json={
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
            },
            timeout=15.0,
        )
        if resp.status_code in (402, 429):
            raise QuotaExceeded(f"{self.name}: API сообщил об исчерпании квоты")
        resp.raise_for_status()
        data = resp.json()
        self.quota.record(cost=1)
        return [
            SearchHit(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("content", ""),
            )
            for item in data.get("results", [])
        ]

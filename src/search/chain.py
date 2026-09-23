"""Fallback-цепочка провайдеров (issue #15, ADR-002; порядок — ADR-011,
доп. issue #178).

Порядок: Firecrawl (первый, работает из рабочей сети, free tier без
карты) → Brave → Tavily (фолбэк; оба недоступны в текущей среде, но
код остаётся на случай смены сети/тарифов). Google CSE закрыт для
новых регистраций (см. ADR-002, "Уточнения" 2026-08-26).
"""
from __future__ import annotations

from datetime import datetime

from .base import QuotaExceeded, SearchHit, SearchProvider


class SearchProviderChain:
    def __init__(self, providers: list[SearchProvider]) -> None:
        if not providers:
            raise ValueError("Нужен хотя бы один провайдер")
        self.providers = providers

    def search(
        self, query: str, max_results: int = 10,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> list[SearchHit]:
        extra = {}
        if date_from:
            extra["date_from"] = date_from
        if date_to:
            extra["date_to"] = date_to
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.search(query, max_results=max_results, **extra)
            except QuotaExceeded as exc:
                errors.append(str(exc))
                continue
        raise QuotaExceeded(
            "Все провайдеры исчерпали квоту: " + "; ".join(errors)
        )

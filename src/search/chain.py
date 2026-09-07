"""Fallback-цепочка провайдеров (issue #15, ADR-002).

Сейчас в проекте активен только Tavily — Google CSE закрыт для новых
регистраций, Brave требует карту (см. ADR-002, "Уточнения" 2026-08-26).
Цепочка из одного элемента уже пригодна для добавления следующих
провайдеров без изменения вызывающего кода.
"""
from __future__ import annotations

from .base import QuotaExceeded, SearchHit, SearchProvider


class SearchProviderChain:
    def __init__(self, providers: list[SearchProvider]) -> None:
        if not providers:
            raise ValueError("Нужен хотя бы один провайдер")
        self.providers = providers

    def search(self, query: str, max_results: int = 10) -> list[SearchHit]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.search(query, max_results=max_results)
            except QuotaExceeded as exc:
                errors.append(str(exc))
                continue
        raise QuotaExceeded(
            "Все провайдеры исчерпали квоту: " + "; ".join(errors)
        )

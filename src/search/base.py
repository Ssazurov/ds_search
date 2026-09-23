"""Интерфейс поискового провайдера (issue #15, ADR-002).

query -> список SearchHit. Реализации не должны обходить это API
скрапингом SERP (ADR-002 п.1) — только официальные Search API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class QuotaExceeded(Exception):
    """Провайдер исчерпал дневную/месячную квоту — пробуем следующего."""


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str


class SearchProvider(ABC):
    name: str

    @abstractmethod
    def search(
        self, query: str, max_results: int = 10,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> list[SearchHit]:
        """Выполнить запрос. date_from/date_to — необязательный период публикации
        (провайдеры фильтруют с точностью до дня). Бросает QuotaExceeded при исчерпании лимита."""
        raise NotImplementedError

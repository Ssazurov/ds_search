"""Добавление статьи в новости (LLM-черновик) — общее для UI (issue #183, #351).

Обёртка над src.news.collect.add_single_url: та же проверка лицензии домена,
дедуп по news_items.source_url и LLM-черновик (requires_review=True).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

RESULT_MESSAGES = {
    "drafted": ("success", "Добавлено черновиком в «Новости» (needs_review)"),
    "skipped_duplicate": ("info", "Такая ссылка уже есть в «Новостях»"),
    "license_denied": ("warning", "Домен не прошёл проверку лицензии (issue #3) — проставьте статус на вкладке «Источники»"),
    "download_failed": ("error", "Не удалось скачать/распарсить страницу"),
    "llm_failed": ("error", "LLM не смог собрать черновик по этому тексту (детали — в логе ds-search)"),
    "llm_unavailable": ("error", "LLM недоступен (endpoint/таймаут) — проверьте Ollama и NEWS_LLM_ENDPOINT"),
    "not_relevant": ("info", "LLM счёл новость нерелевантной теме — не добавлено"),
}


def describe(status: str) -> tuple[str, str]:
    """(уровень st.*, текст) по статусу add_single_url."""
    return RESULT_MESSAGES.get(status, ("error", status))


def add_articles_as_news(
    articles: Iterable[dict], add: Callable | None = None,
) -> list[tuple[str, str]]:
    """articles: [{url, title}]. Возвращает [(заголовок/URL, статус)].
    Ошибка одной статьи не прерывает остальные."""
    if add is None:
        from src.news.collect import add_single_url as add
    results = []
    for a in articles:
        label = a.get("title") or a["url"]
        try:
            status = asyncio.run(add(a["url"], title=a.get("title") or ""))
        except Exception as exc:  # noqa: BLE001
            status = f"Ошибка: {exc}"
        results.append((label, status))
    return results


@dataclass
class NewsOutcome:
    """Итог пакетной отправки в новости (issue #398)."""
    finalized: list[int] = field(default_factory=list)  # индексы drafted/skipped_duplicate
    ok: int = 0
    drafted: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)  # "label: текст"

    @property
    def stats(self) -> dict[str, int]:
        out: dict[str, int] = {}
        if self.drafted:
            out["черновиков"] = self.drafted
        if self.duplicates:
            out["уже были"] = self.duplicates
        return out


def summarize(results: list[tuple[str, str]]) -> NewsOutcome:
    """results — вывод add_articles_as_news, порядок совпадает с исходными статьями."""
    out = NewsOutcome()
    for i, (label, status) in enumerate(results):
        if status == "drafted":
            out.drafted += 1
        elif status == "skipped_duplicate":
            out.duplicates += 1
        else:
            out.errors.append(f"{label}: {describe(status)[1]}")
            continue
        out.finalized.append(i)
        out.ok += 1
    return out

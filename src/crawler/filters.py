"""Кастомные фильтры релевантности для Crawl4AI (issue #2, #8).

BestFirstCrawlingStrategy + KeywordRelevanceScorer ранжирует очередь ссылок
по совпадению с ключевыми словами направления. FilterChain отсекает
служебные/листинговые URL до скачивания (issue #8 / ADR-001 п.3b).
PruningContentFilter (fit_markdown) даёт hard-cutoff порог релевантности
контента перед сохранением — переиспользуется механизм issue #6.
"""
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from crawl4ai.deep_crawling.filters import (
    FilterChain,
    DomainFilter,
    URLPatternFilter,
    ContentTypeFilter,
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.content_filter_strategy import PruningContentFilter

# Базовые паттерны, не зависящие от источника: бинарные файлы и пагинация
# (issue #8 п.2 — параметры вида ?PAGEN_1=N, ?PAGE=N, ?page=N).
BASE_EXCLUDE_PATTERNS = [
    "*.jpg", "*.png", "*.zip",
    "*PAGEN_1=*", "*PAGE=*", "*page=*",
]

# Query-параметры, которые не влияют на идентичность контента страницы и
# должны вычищаться перед хэшированием (issue #8, дедуп из ручного разбора
# корпуса: "Главная страница" x3 и т.п.).
_TRACKING_PARAMS_PREFIXES = ("utm_", "yclid", "gclid", "fbclid", "_openstat")
_SESSION_PARAMS = {"PHPSESSID", "sessid", "sid"}


def canonicalize_url(url: str) -> str:
    """Нормализует URL для дедупликации: убирает fragment, tracking/session
    query-параметры, приводит trailing slash (issue #8)."""
    parts = urlsplit(url)
    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.startswith(_TRACKING_PARAMS_PREFIXES) and k not in _SESSION_PARAMS
    ]
    query = urlencode(sorted(kept))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def build_exclude_patterns(exclude_slugs: tuple[str, ...]) -> list[str]:
    slug_patterns = [f"*/{slug}/*" for slug in exclude_slugs]
    slug_patterns += [f"*/{slug}" for slug in exclude_slugs]
    return BASE_EXCLUDE_PATTERNS + slug_patterns


def build_filter_chain(domain: str, exclude_slugs: tuple[str, ...] = ()) -> FilterChain:
    return FilterChain([
        DomainFilter(allowed_domains=[domain]),
        URLPatternFilter(patterns=build_exclude_patterns(exclude_slugs), reverse=True),
        ContentTypeFilter(allowed_types=["text/html", "application/pdf"]),
    ])


def build_relevance_scorer(keywords: list[str]) -> KeywordRelevanceScorer:
    return KeywordRelevanceScorer(keywords=keywords, weight=1.0)


def build_content_filter() -> PruningContentFilter:
    """issue #8 п.4 / issue #6: density-based фильтр контента, отдаёт
    result.markdown.fit_markdown. Порог по длине fit_markdown (не отдельная
    метрика) — короткий/пустой fit_markdown = листинг/навигация."""
    return PruningContentFilter()


_PDF_LINK_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)


def find_pdf_teaser_link(html: str) -> str | None:
    """issue #8 п.3: страница-тизер к PDF-отчёту — ищем прямую ссылку на PDF
    в разметке карточки ("скачать отчёт")."""
    m = _PDF_LINK_RE.search(html or "")
    return m.group(1) if m else None

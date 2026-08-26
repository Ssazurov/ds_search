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
    # поддомены (напр. dnevnik-razvitiya-rebenka.downsideup.org) — отдельные
    # сервисы, не статьи; DomainFilter по basedomain их не отсекает.
    "https://*.downsideup.org/*",
    # главная страница ресурса, если не является posted seed-статьёй.
    "https://downsideup.org/",
    # bare-root листинговые страницы категорий ("Все материалы" + список
    # ссылок, не статья) — известные из ручного разбора корпуса.
    "https://downsideup.org/analytics/",
    "https://downsideup.org/analytics",
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
_TEASER_MARKER_RE = re.compile(
    r"скачать отчёт|скачать отчет|открыть отчёт|открыть отчет", re.IGNORECASE
)


def find_pdf_teaser_link(html: str) -> str | None:
    """issue #8/#11: страница-тизер к PDF-отчёту — ищем прямую ссылку на PDF
    в разметке карточки ("скачать отчёт"/"открыть отчёт")."""
    m = _PDF_LINK_RE.search(html or "")
    return m.group(1) if m else None


def is_pdf_teaser_page(html: str) -> bool:
    """issue #11: признак карточки-тизера — рядом с .pdf-ссылкой есть маркер
    "скачать/открыть отчёт". Проверяется независимо от длины fit_markdown:
    у такой карточки часто есть блок "Похожие материалы" (список ссылок),
    из-за которого fit_markdown легко проходит min_fit_markdown_chars, хотя
    реального текста статьи нет."""
    html = html or ""
    return bool(_PDF_LINK_RE.search(html) and _TEASER_MARKER_RE.search(html))


_MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")


def link_to_text_ratio(markdown_text: str) -> float:
    """issue #6/ADR-001 п.3a: доля символов markdown-ссылок в тексте.
    Каталожные/листинговые страницы (список подкатегорий/книг/интервью с
    коротким описанием) почти целиком состоят из ссылок — ratio 0.45-0.9 на
    ручной проверке корпуса downsideup; реальные статьи — ratio ~0.05-0.15."""
    text = markdown_text or ""
    if not text.strip():
        return 0.0
    link_chars = sum(len(m) for m in _MD_LINK_RE.findall(text))
    return link_chars / len(text)


# Порог LTR подобран на ручном разборе 8 "мусорных" страниц корпуса
# downsideup 2026-08-25 (issue #6): 6/8 листингов дали 0.48-0.86,
# 1 реальная статья — 0.05. 0.3 — с запасом между кластерами.
LTR_CUTOFF = 0.3


def is_listing_page(fit_markdown: str) -> bool:
    """issue #6: hard-cutoff по link-to-text ratio — отсекает
    каталожные/листинговые страницы, которые проходят фильтр по длине
    fit_markdown (min_fit_markdown_chars), но не содержат связного текста
    статьи, только вводный абзац + список ссылок на подкатегории/материалы."""
    return link_to_text_ratio(fit_markdown) > LTR_CUTOFF

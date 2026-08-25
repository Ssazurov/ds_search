"""Кастомные фильтры релевантности для Crawl4AI (issue #2).

BestFirstCrawlingStrategy + KeywordRelevanceScorer ранжирует очередь ссылок
по совпадению с ключевыми словами направления. Порог отсекает нерелевантные
страницы (напр. новости/контакты) до скачивания.
"""
from crawl4ai.deep_crawling.filters import (
    FilterChain,
    DomainFilter,
    URLPatternFilter,
    ContentTypeFilter,
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer


EXCLUDE_PATTERNS = [
    "*/news/*", "*/events/*", "*/contacts/*", "*/search*",
    "*.jpg", "*.png", "*.zip",
]


def build_filter_chain(domain: str) -> FilterChain:
    return FilterChain([
        DomainFilter(allowed_domains=[domain]),
        URLPatternFilter(patterns=EXCLUDE_PATTERNS, reverse=True),
        ContentTypeFilter(allowed_types=["text/html", "application/pdf"]),
    ])


def build_relevance_scorer(keywords: list[str]) -> KeywordRelevanceScorer:
    return KeywordRelevanceScorer(keywords=keywords, weight=1.0)

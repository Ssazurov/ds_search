"""Discovery: search_provider abstraction (issue #15, ADR-002)."""
from .base import SearchHit, SearchProvider, QuotaExceeded
from .brave import BraveProvider
from .chain import SearchProviderChain
from .firecrawl import FirecrawlProvider
from .tavily import TavilyProvider

__all__ = [
    "SearchHit",
    "SearchProvider",
    "QuotaExceeded",
    "SearchProviderChain",
    "BraveProvider",
    "FirecrawlProvider",
    "TavilyProvider",
]

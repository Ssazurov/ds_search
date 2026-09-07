"""Discovery: search_provider abstraction (issue #15, ADR-002)."""
from .base import SearchHit, SearchProvider, QuotaExceeded
from .chain import SearchProviderChain
from .tavily import TavilyProvider

__all__ = [
    "SearchHit",
    "SearchProvider",
    "QuotaExceeded",
    "SearchProviderChain",
    "TavilyProvider",
]

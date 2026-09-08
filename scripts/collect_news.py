"""CLI: один прогон автосбора новостей (issue #61) — SearchChain ->
dedup -> download -> LLM-draft -> news_items status=draft.

Использование: python -m scripts.collect_news

Cron (раз в час), пример строки для crontab:
    0 * * * *  cd /home/vector/ds/ds_search && .venv/bin/python -m scripts.collect_news >> data/news_collect.log 2>&1
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.news.collect import collect_news
from src.search.chain import SearchProviderChain
from src.search.tavily import TavilyProvider


def main() -> None:
    chain = SearchProviderChain([TavilyProvider()])
    stats = asyncio.run(collect_news(chain))
    for k, v in stats.as_dict().items():
        print(f"{k}={v}")
    if stats.errors:
        print(f"errors={len(stats.errors)}:", file=sys.stderr)
        for e in stats.errors:
            print(f"  {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

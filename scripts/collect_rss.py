"""CLI: RSS-адаптер автосбора новостей (issue #157, эпик #156, ADR-010) —
фиды (config/rss_sources.yaml) -> фильтр свежести -> dedup -> download ->
LLM-draft -> news_items status=draft. Тот же пайплайн, что и
scripts/collect_news.py (issue #61), другой источник кандидатов.

Использование:
    python -m scripts.collect_rss                # свежесть 5 дней (issue #158, по умолчанию)
    python -m scripts.collect_rss --days 30       # ручной запуск за период N дней (issue #159)
    python -m scripts.collect_rss --days 0        # без фильтра свежести

Cron (раз в день, отдельно от collect_news.py):
    0 6 * * *  cd /home/vector/projects/ds/ds_search && .venv/bin/python -m scripts.collect_rss >> data/rss_collect.log 2>&1
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.news.collect import collect_rss


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, default=5,
        help="фильтр свежести в днях (issue #158); 0 = без фильтра (issue #159)",
    )
    args = parser.parse_args()
    max_age_days = None if args.days <= 0 else args.days

    stats = asyncio.run(collect_rss(max_age_days=max_age_days))
    for k, v in stats.as_dict().items():
        print(f"{k}={v}")
    if stats.errors:
        print(f"errors={len(stats.errors)}:", file=sys.stderr)
        for e in stats.errors:
            print(f"  {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

"""CLI: штатная загрузка одной новости по ссылке пользователя (issue #183).

Использование: python -m scripts.add_news_by_url <url>

Переиспользует пайплайн автосбора (src/news/collect.py, issue #61):
license-гейт (config/licenses.yaml, issue #3), краулер и LLM-классификацию
по категориям СД. Результат попадает в news_items со статусом draft — тем
же потоком needs_review, что и автосбор/RSS (issue #159).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.news.collect import add_single_url

_MESSAGES = {
    "drafted": "OK: новость добавлена черновиком (news_items, status=draft)",
    "skipped_duplicate": "Пропущено: такой source_url уже есть в news_items",
    "license_denied": (
        "Отклонено: домен не прошёл проверку лицензии "
        "(config/licenses.yaml, issue #3) — добавьте домен в реестре, если нужно продолжить"
    ),
    "download_failed": "Ошибка: не удалось скачать/распарсить страницу (или это PDF без текста)",
    "llm_failed": "Ошибка: LLM не смог собрать черновик по этому тексту",
}


def main() -> None:
    if len(sys.argv) != 2:
        print("Использование: python -m scripts.add_news_by_url <url>", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1]
    result = asyncio.run(add_single_url(url))
    print(_MESSAGES.get(result, result))
    sys.exit(0 if result == "drafted" else 1)


if __name__ == "__main__":
    main()

## Issue
Closes #61

## Зависимость
База ветки — `feat/issue-49-news-publish` (PR #60), не `main`: нужен
`src/news/publish.py`, которого ещё нет в main. Мёржить после PR #60.

## Что сделано
- `src/news/collect.py`: `collect_news()` — SearchChain -> dedup (по
  `news_items.source_url`, до скачивания/LLM) -> `discovery.download.
  download_single` (переиспользован ради license-гейта check_license,
  ADR-001 п.3) -> `llm_draft.generate_draft` -> `db.insert_news_item`.
  Ошибка одного источника или одного query не роняет весь прогон.
  Намеренно НЕ пишет в `discovered_sources`/GAR (ADR-002 очередь для
  ручной курации основного корпуса) — см. ADR-003 "Уточнение issue #61".
- `src/news/db.py`: `source_url_exists()` — дедуп-проверка перед
  download+LLM.
- `config/news_search_queries.yaml` — темы поиска, не хардкод.
- `scripts/collect_news.py` — CLI для cron (`python -m scripts.collect_news`),
  пример crontab-строки в докстринге.
- ADR-003 дополнен, запись в docs/decisions.md.

## Тесты
`tests/test_news_collect.py` — 7 тестов (happy path, дедуп до скачивания,
license_denied, download/LLM-ошибка не роняет прогон, QuotaExceeded одного
query не роняет остальные, чтение YAML-конфига). `pytest -q`: 77/77.

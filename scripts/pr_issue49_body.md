parent: #44 (Epic новостной блок)
Closes #49

## Что сделано
- `src/news/db.py`: миграция колонок `gar_document_id`/`publish_error`, `set_publish_result()`.
- `src/news/publish.py`: `GarNewsClient` (ensure_dataset/ingest_document), `build_content_md()`,
  `build_metadata()` (doc_type=news, license=own_generated), `publish_news_item()` — идемпотентно,
  ошибка GAR пишется в `publish_error`.
- `scripts/publish_news.py` — CLI батч для cron/бэкфилла.
- `ui/news_tab.py`: кнопка "Опубликовать" публикует в GAR сразу, "Переотправить в GAR" при ошибке.
- ADR-003 дополнен разделом "Уточнение 2026-09-08": ds_site своего контента не хранит, публикация ==
  ingestion в GAR, отдельного push-API в сайт нет.

## Проверка
- `pytest tests/test_news_publish.py` — 9 новых тестов (build_content/build_metadata, happy path на
  fake-клиенте, идемпотентность, force, missing/wrong status, запись ошибки).
- Полный набор: `pytest -q` — 70/70.
- Не проверено: реальный вызов gar-core-api `/ingestion/documents` (сервис не поднят в этой сессии) —
  только фейковый клиент в тестах.

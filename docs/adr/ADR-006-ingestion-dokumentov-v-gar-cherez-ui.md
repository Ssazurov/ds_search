# ADR-006: Ingestion документов в GAR через UI (одиночно и пакетом)

Дата: 2026-09-12
Статус: принято

## Контекст

Скачивание материала (`data/raw/**.md`+`.json`) и его попадание в GAR/RAG —
два разных шага. Первый штатно доступен в UI (вкладка «Загрузка»). Второй
сейчас доступен только для новостей (`src/news/publish.py` →
`GarNewsClient`, HTTP напрямую в gar-core-api `/ingestion/*`). Для обычных
документов ingestion делают только через `ds_ingestion` CLI, и только
**папкой целиком** — нет режима «один файл». Дашборд и Documents tab
показывают метрику «В GAR» как `0`/`not_started` — открытый вопрос
ADR-002 п.7 («нет сигнала от ds_ingestion»).

## Решение

1. **Не переиспользуем `ds_ingestion` CLI** для UI-инициированной загрузки:
   он в отдельном репозитории/процессе, требует полной схемы датасета,
   не поддерживает единичный файл. Вместо этого обобщаем уже работающий
   HTTP-паттерн из `news/publish.py`.
2. Выносим `GarNewsClient` → общий `GarIngestClient` в
   `src/gar_ingest/client.py` (settings/ensure_dataset/ingest_document/
   `GarPublishError`), `news/publish.py` переиспользует его без изменения
   поведения.
3. Новая функция `ingest_document(doc_json_path, force=False)` в
   `src/gar_ingest/documents.py`: читает sidecar `.json` в `data/raw/**`,
   грузит content_path в GAR, пишет `gar_document_id`/`ingested_at`/
   `ingest_error` обратно в тот же `.json` (файл — источник состояния,
   отдельной таблицы docs нет, в отличие от `news_items`).
4. Идемпотентность: как в `publish_news_item` — skip если
   `gar_document_id` уже есть и `force=False`.
5. UI (`ui/documents_tab.py`): кнопка «Загрузить в GAR» на строку
   документа (одиночно) + кнопка «Загрузить все не загруженные» (пакетно,
   по текущему фильтру направления/категории, с прогресс-баром).
6. Дашборд: метрика «В GAR» считается фактически (доля `.json` с
   `gar_document_id`) — закрывает открытый вопрос ADR-002 п.7.

## Последствия

- Общий HTTP-клиент к gar-core-api вместо двух копий (news + docs).
- Ingestion для corpus-документов становится доступен без похода в WSL/CLI.
- `ds_ingestion` CLI остаётся для холодного bulk-импорта (полная папка,
  bootstrap схемы), не для точечной догрузки.

# ADR-007: Автозаполнение GAR-поля keywords фоновым джобом

Дата: 2026-09-12
Статус: принято

## Контекст

GAR-поле `keywords` (text, активно в схеме датасета `sindrom-dauna`) сейчас
нигде не заполняется: ни `src/metadata/classify.py` (LLM-классификатор
select-полей, issue #91), ни `download_single`/`crawler._save` его не
формируют — они закрывают только select-поля (age/target_audience/
direction/category/doc_type).

## Решение

Согласовано с пользователем 2026-09-12: **не** тянуть keywords в
pre-upload пайплайн (`download.py`/`classify.py`). Вместо этого — отдельный
фоновый процесс, который проставляет keywords уже загруженным в GAR
документам:

1. `src/gar_ingest/client.py` дополнен тремя методами (переиспользуют тот
   же `httpx.Client`, что `ensure_dataset`/`ingest_document`):
   - `list_documents(dataset_id, status="indexed")` — `GET /ingestion/documents`;
   - `get_document_text(document_id)` — канонический markdown документа
     (`GET /ingestion/documents/{id}/assets/canonical-md`), `""` при 404;
   - `patch_document_metadata(document_id, metadata)` — `PATCH
     /ingestion/documents/{id}`; сервер (`document_edit_service.update_document`)
     мержит переданный dict с существующей metadata, так что достаточно
     передавать только `{"keywords": ...}`.
2. `src/metadata/keywords_worker.py`: `process_dataset(dataset_name=,
   limit=, force=, dry_run=)` — проходит документы датасета со
   `status="indexed"`, для тех, у кого `metadata.keywords` пусто (или
   всегда при `--force`), тянет текст, извлекает keywords через LLM и
   пишет обратно PATCH'ем. Ошибка на одном документе не роняет джоб —
   собирается в `summary["errors"]`.
3. Извлечение — отдельный LLM-конфиг `config/keywords_llm.yaml` (формат
   `LlmConfig` из `src/news/llm_draft.py`, переиспользуется `call_llm`),
   не `classify_llm.yaml`: другой промпт (свободный список ключевых слов,
   не select-поле из схемы), не хотим менять поведение классификатора
   select-полей при подстройке промпта под keywords.
4. Запуск — вручную/по расписанию через CLI
   (`python -m src.metadata.keywords_worker [--dataset][--limit][--force][--dry-run]`),
   без встроенного планировщика в этом issue — periodic job (cron/systemd
   timer) заводится отдельно при развёртывании.

## Последствия

- `keywords` заполняется асинхронно после ingestion, не блокирует и не
  замедляет pre-upload пайплайн (download/classify).
- Повторный прогон джоба идемпотентен по умолчанию (пропускает документы
  с уже непустым `keywords`), `--force` — для пересчёта.
- Источник правды по `keywords` — сам GAR (PATCH мержит metadata), sidecar
  `.json` в `data/raw/**` не трогается и не хранит keywords.
- Требует доступный `gar-core-api` (list/canonical-md/patch эндпоинты уже
  существуют, ingestion.py) и рабочий LLM-эндпоинт (тот же прокси-паттерн,
  что и `classify_llm.yaml`/`news_llm.yaml`, см. CURRENT_STATUS 2026-09-12).

# ADR-0009: Реальный re-crawl источника перед GAR reload

Статус: Accepted  
Дата: 2026-09-14  
Затронуты: `ds_search`, `ds_ingestion`; `ds_site` не изменяется

## Контекст

ADR-0007/0008 задали reload по существующему `gar_document_id`, но текущий
оркестратор может переиндексировать уже сохранённый sidecar вместо фактического
получения свежего источника. Нужен безопасный ручной workflow для исправления
контента и обновления metadata без потери provenance, ручных правок или ссылок.

## Решение

1. `ds_search` выполняет точечный re-crawl по canonical URL. URL берётся из
   sidecar (`source_url`, затем `canonical_url`); canonical URL — identity.
   Результат crawler сохраняет в отдельный staging-каталог, не перезаписывая рабочий
   `.md`/`.json` до прохождения валидации.
2. Результат crawler передаётся как структурированный JSON-контракт с
   `source`, `doc_id`, `canonical_url`, staged content/metadata paths,
   provenance и correlation ID. Человекочитаемый stdout не является API.
   `doc_id` проверяется как `sha256(canonical_url)[:16]`; изменение ID — отказ.
3. `ds_ingestion` валидирует staged пару, canonical URL, стабильность doc_id,
   обязательные metadata, license/filter outcomes и provenance. Только после
   успешной валидации staging публикуется атомарно, с backup прежних файлов.
4. Provenance merge: source-managed non-null значения из нового результата
   заменяют старые; непустые GAR metadata, отсутствующие в новом результате,
   сохраняются как ручные и попадают в `preserved_fields`. Явный `null` не
   удаляет старое значение; удаления требуют отдельного tombstone-контракта.
   Для каждого поля логируются source (`crawl`, `manual-preserved`) и изменение.
5. GAR обновляется in-place строго по существующему `gar_document_id`: сначала
   PATCH metadata, затем PUT content. Delete+recreate и `supersedes` запрещены.
   `document_id` и state mapping не меняются.
6. При сбое crawl/validation GAR и рабочие raw-файлы не меняются. При сбое PUT
   после успешного PATCH оркестратор пытается PATCH snapshot старой metadata.
   Успешный rollback возвращает `partial_failure`; неуспешный rollback создаёт
   `manual_recovery` с correlation ID, сохраняет backup и не обновляет state.
7. Конкурентные reload блокируются per `gar_document_id` (связанный `doc_id`);
   занятый lock возвращает HTTP 409. Существующие auth/rate-limit ADR-0008
   остаются обязательными.
8. `ds_site` не участвует: существующая Streamlit-кнопка в `ds_search` остаётся
   точкой входа и показывает этап, typed failure и correlation ID.

## Альтернативы

- Delete+recreate или `supersedes`: отклонено, ломает стабильные ссылки,
  retrieval scope и downstream provenance.
- Перезапись raw до validation: отклонено, лишает rollback и сохраняет битый
  результат.
- Молчаливое удаление metadata по `null`: отклонено, теряет ручную редактуру.
- Параллельный reload одного документа: отклонено, создаёт race PATCH/PUT.

## Последствия

- Нужен staged crawler adapter/CLI в `ds_search`.
- Нужна orchestration/validation/rollback/lock реализация в `ds_ingestion`.
- GAR API должен поддерживать уже существующие PATCH metadata и PUT content
  in-place; новый GAR endpoint не требуется.
- Требуются focused tests и live smoke с проверкой стабильного ID, provenance,
  rollback и порядка PATCH-before-PUT.

## Связи

- ADR-0007: full source reload pipeline
- ADR-0008: auth/rate-limit для reload
- Требования: `../requirements/real-source-recrawl-reload.md`

# Требования: real-source re-crawl и GAR reload

Статус: готово к реализации  
ADR: [ADR-0009](../adr/0009-real-source-recrawl-reload.md)  
Затронуты: `ds_search`, `ds_ingestion`; `ds_site` вне scope

## Цель

Кнопка/команда reload должна заново получить конкретный источник, проверить
результат и безопасно обновить существующий GAR-документ, сохранив provenance,
ручные metadata и неизменный `document_id`.

## Функциональные требования

1. **Crawl.** Поиск URL: `source_url`, fallback `canonical_url`. Выполнять
   существующие license, thin, catalog и PDF-teaser фильтры. Ошибки сети,
   timeout, license-denied и filter rejection — typed failure; GAR не меняется.
2. **Staging.** Сохранять `.md` и `.json` в отдельный staging directory. До
   валидации не менять рабочие raw/state. Успешный staged результат содержит
   `source`, `doc_id`, `canonical_url`, paths, metadata, provenance и
   `correlation_id`. CLI stdout — одна JSON-модель; exit 0 только после save.
3. **Validation.** Проверить JSON, content path, обязательные metadata,
   canonical URL и `doc_id = sha256(canonical_url)[:16]`. Любое изменение ID,
   missing content или malformed output — HTTP 422; staged результат не
   публиковать.
4. **Provenance merge.** Сначала получить snapshot старого GAR metadata.
   Source-managed non-null значения нового результата заменяют старые.
   Непустые старые поля, отсутствующие в новом payload, сохраняются как
   `manual-preserved`; explicit `null` не удаляет значение без tombstone.
   Отчёт содержит `changed_fields`, `preserved_fields` и источник каждого поля.
5. **GAR update.** Выполнить PATCH metadata, затем PUT content, оба по тому же
   `gar_document_id`. Delete+recreate и `supersedes` запрещены. State mapping не
   переписывать; `document_id` обязан остаться прежним.
6. **Rollback.** При crawl/validation/PATCH failure рабочие raw, state и GAR
   остаются прежними. После успешного PATCH и неуспешного PUT выполнить PATCH
   старого metadata snapshot. Вернуть `partial_failure` при успешном rollback;
   при неуспешном rollback вернуть `manual_recovery`, сохранить backup и
   correlation ID, state не обновлять.
7. **Locking.** Один lock на `gar_document_id`/связанный `doc_id`. Второй
   одновременный reload получает HTTP 409. Lock освобождать при любом исходе.
8. **API/UI.** Сохранить `POST /reload` и `/reload_by_gar_id`, auth и rate-limit
   ADR-0008. Ответы: success report, 404 mapping, 409 lock/conflict, 422
   validation, 429 rate-limit, 502 crawler/GAR failure. Streamlit показывает
   безопасное сообщение, этап и correlation ID; traceback наружу не отдавать.
9. **ds_site.** Application code не менять; сайт продолжает читать стабильный
   GAR ID и существующий public contract.

## Acceptance criteria

- Mocked tests покрывают URL resolution, staged no-overwrite, typed CLI JSON,
  validation, provenance merge включая null, stable ID, PATCH-before-PUT,
  metadata rollback, backup/state behavior, lock/409 и HTTP mappings.
- Live smoke на временном документе подтверждает новый content/index,
  прежний `document_id` и сохранённые ручные metadata.
- Focused tests, `git diff --check` проходят; application code этой постановкой
  не изменяется.

## Не входит

Массовый recrawl, новый публичный сайт/API, delete/recreate GAR documents,
изменение retrieval/generation, новый tombstone schema или новый GAR endpoint.

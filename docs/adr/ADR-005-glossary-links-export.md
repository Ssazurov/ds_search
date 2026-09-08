# ADR-005: Экспорт глоссария и справочника ссылок (issue #25)

Дата: 2026-09-08. Статус: принято. Эпик: #23 (ADR-004).

## Контекст
Источники: `data/downsyndrome_glossary.xlsx` (лист «Глоссарий СД», 117
терминов; лист «IT» — техтермины стартапа, в паблик не идут),
`data/sites_ru_down_syndrome.xlsx` (137 сайтов-ресурсов). Нужно: (1)
данные для статичных страниц `ds_site` (ADR-004, SSG), (2) те же данные —
в RAG-корпус GAR, чтобы чат-виджет мог отвечать по ним.

## Решение
- `scripts/export_glossary_links.py`: xlsx -> `data/exports/glossary.json`
  (id/term/definition/en/category), `data/exports/links.json`
  (name/url/age/description/region/category/relevance) — забирает
  `ds_site` при сборке (git submodule/copy — вне ds_search).
- Для RAG: два агрегированных документа (не 117+137 мелких — глоссарий/
  справочник как единое целое консистентнее для чата), sidecar-формат
  идентичен `data/raw/<source>/*.json+*.md` (issue #5 адаптер):
  `data/raw/glossary/glossary.json+.md`, `data/raw/links/links.json+.md`.
- `license=own_generated` (свой составленный контент, не скрейпинг —
  ADR-001 гейт не применим), `source_url=internal://ds_search/<slug>`
  (нет единого внешнего URL), `direction=methodology`,
  `category=inclusion` (ближайшая существующая категория).
- `doc_type`: `glossary`, `resource_directory` — добавлены в
  `config/categories.yaml` (это справочник UI, не enum бэкенда — см.
  `src/metadata/schema.py`, backend валидирует только `license`).

## Альтернативы
- 117+137 отдельных документов в RAG — отклонено: overhead курации/
  ре-run без выигрыша в качестве ответа чата на этом объёме.
- Публиковать без `content_path` (только JSON) — отклонено: адаптер
  ds_ingestion требует `content_path` на файл для gar-docling-intake.

## 2026-09-12 -- issue #128: индексация glossary/links в GAR через ingestion-пайплайн

- `python -m src.adapter.cli glossary` / `links` успешно загрузили оба
  агрегированных документа (ADR-005) в датасет `sindrom-dauna`
  (`81f35f18-8d32-458e-bf33-ddb68349e015`), `status: indexed`, видны в
  `/public/documents` (ds_site).
- Сопутствующий фикс в ds_ingestion (Ssazurov/ds_ingestion#4): `_load_domain_schema`
  падал `ImportError` на relative-импорт в `ds_search/src/metadata/schema.py` —
  модуль грузился через `importlib` без пакета-родителя. Больше не наш баг,
  но если снова меняется способ загрузки схемы отсюда для ds_ingestion —
  учитывать, что `schema.py` делает `from .profile import ...`.
- `data/raw/{glossary,links}/*.json` (не в git, `data/` в `.gitignore`)
  скорректированы под контролируемые select-поля GAR: `target_audience`
  — одно значение, не CSV; `age` — добавлена опция `"Все возрасты"` в
  поле `age` датасета (её не было); `category`/`doc_type` — убраны
  (значений `inclusion`/`glossary`/`resource_directory` нет в словаре
  GAR, оба поля необязательные).
- Датасет `sindrom-dauna` больше НЕ пустой (была известной проблемой
  ds_ingestion#3) — сейчас 4 документа: alisa-i-chudesa,
  bez-oglyadki-na-diagnoz, glossary, links.

Полная история до 2026-08-24 перенесена в
`docs/archive/current-status/CURRENT_STATUS-2026-08-24_2026-09-10.md`.

## 2026-09-12 -- issue #127: маппинг glossary/links в схему фильтров сайта (эпик #126)

- Новый `src/metadata/glossary_links_mapping.py`: `map_glossary_item()` /
  `map_link_item()` — по-элементный маппинг category/age из
  `data/exports/glossary.json`/`links.json` в direction/category/doc_type/
  target_audience/age (активные опции GAR, `gar_schema.py`).
- `GLOSSARY_CATEGORY_MAP` (6/6 категорий) и `LINK_CATEGORY_MAP` (25/25,
  включая соцсети) покрывают все текущие значения — проверено скриптом
  сверки с `data/exports/*.json` и `category_options_for_direction()`
  (0 непокрытых категорий, 0 невалидных пар direction/category).
- `doc_type` = `glossary_term`/`link` по требованию issue, но этих значений
  ещё нет среди активных опций поля `doc_type` в GAR
  (`config/gar_schema_cache.json`) — **блокер для #128**, нужно
  завести/активировать на стороне GAR перед индексацией.
- `age`: однозначно мапится только `"18+" -> "18+ лет"`; "Все"/"Дети"/
  "Взрослые" оставлены `None` (needs_review) — не угадываем жизненный этап.
- `region`/`relevance` из links.json сознательно не переносятся — не входят
  в целевую схему фильтров (direction/category/doc_type/age/target_audience).
- `target_audience` = `"parents"` везде (было некорректной comma-строкой
  "parents,specialists" в старом профиле — поле single-select).
- `gar_mapping.py`/`classify.py` менять не потребовалось: doc_type там
  тянется динамически из схемы GAR (`_SELECT_FIELDS`), правки не нужны,
  пока новые опции не заведены на стороне GAR.
- `tests/test_glossary_links_mapping.py` — 5 passed.
- Готово к использованию в #128 (per-item ingestion glossary/links в GAR).

## 2026-09-12 -- UI: кнопки "Загрузить в GAR" в documents_tab (issue #116, ADR-006 п.5)

- `ui/documents_tab.py`: кнопка на строку документа (одиночная ingestion через
  `src.gar_ingest.documents.ingest_document`) + кнопка "Загрузить все не
  загруженные" по текущему фильтру направление/источник, с прогресс-баром.
- Фильтры направление/источник добавлены (`_apply_filters`).
- Колонка `ingested` в таблице теперь по факту `gar_document_id` в sidecar
  `.json` (done/error/not_started), а не хардкод `not_started`.
- Ошибки ingestion — `st.error` с текстом исключения (`ingest_error` пишется
  в sidecar `.json` самой `ingest_document`), батч не падает целиком.
- Метрика "В GAR" на dashboard_tab.py — отдельная задача, issue #117.
- PR #124 (squash-merge в main), depends on #115 (closed).
- Проверено: `py_compile`, импорт модуля, `pytest -k document` (9 passed).

## 2026-09-12 -- интеграция классификатора в download_single

- `src/discovery/download.py`: после успешного сохранения `.md` и `.json`
  вызывается `scripts.classify_article.classify_article(md_path)`, который
  возвращает `direction` и `category` из `gar-core-api/docs/Направления_Категории_СД.md`.
- При успехе поля `direction/category` в JSON обновляются на классифицированные.
- При ошибке классификации (LLM недоступен, таймаут, невалидный ответ) —
  ошибка логируется, скачивание не откатывается, `direction/category` остаются
  исходными значениями из `source`.
- Импорт `classify_article` опционален: если `scripts/classify_article.py` или
  его зависимости недоступны, `classify_article = None` и классификация
  пропускается.
- Проверка: `download_single` на `https://downsideup.org/elektronnaya-biblioteka/alisa-i-chudesa`
  с `suggested_direction/category = "family_support"` -> JSON получил
  `direction: "ПОДДЕРЖКА СЕМЬИ"`, `category: "Первая реакция на диагноз (шок, принятие — пре- и постнатально)"`
  вместо заглушки `family_support`.
- Обработка ошибок: при недоступном LLM исходные `direction/category`
  сохраняются в JSON, скачивание завершается успешно.
- Тесты `tests/test_download.py` обновлены: `classify_article` замокан
  в `test_download_single_substantive_saves_md` и
  `test_download_single_preserves_curated_information_architecture`.
- Прогон: `pytest tests/test_download.py` — 12 passed.

## 2026-09-10 -- issue #94: тестовая загрузка test1.md новым пайплайном (эпик #88 закрыт)

- SourceCrawler (не download_single) на одиночном URL (max_pages=1,
  SourceConfig direction=podderzhka-semi, category=issledovaniya-i-opyt-semey
  по gar_mapping family_support) -> data/raw/family_support/test1.md+json.
- needs_review=true: age/target_audience/doc_type=null. LLM недоступна
  в окружении, fallback ушёл на доменный gar_mapping (только direction) --
  dest_dir-специфичный fallback (target_audience/doc_type) не подхватился,
  т.к. _apply_classification зовёт classify() без dest_dir.
- Найдено: нужен доп. фикс -- пробрасывать dest_dir в classify() из
  crawler._save, иначе fallback по dest_dir из gar_mapping мёртвый код
  для основного pipeline. Отдельный issue не заведён.
- Issue #94 закрыт, эпик #88 (6/6) закрыт.

## 2026-09-11 -- issue #103: автоподсветка терминов глоссария

- `src/rag/glossary_highlight.py`: детерминированная подсветка вхождений термина
  Markdown-ссылкой `/glossary/{id}`; longest-first, case-insensitive,
  границы слов; существующие ссылки, inline/fenced code не изменяются.
- `render_answer_markdown()` принимает `glossary_terms` и `glossary_path`.
- Тесты добавлены в `tests/test_rag_export.py`.

## 2026-09-11 -- issue #30: импорт сокращений в GAR

- `scripts/import_glossary_expansions.py` выбирает из `data/ds_glossary.xlsx`
  только сокращения, строит payload `term/expansion/aliases/status/active` для
  `POST /datasets/{id}/glossary-terms`, пропускает уже существующие термины.
- Есть `--dry-run`; dataset берётся из `GAR_DATASET_ID` или ищется по
  `GAR_DATASET_NAME` (по умолчанию `sindrom-dauna`).
- Добавлены тесты выбора сокращений. Реальный POST требует доступный GAR API.

## 2026-09-11 -- классификация статьи по категориям СД

- `scripts/classify_article.py` принимает путь к Markdown-статье, читает категории
  из `gar-core-api/docs/Направления_Категории_СД.md`, вызывает настроенный LLM и
  проверяет, что выбрана ровно одна категория из списка.
- `_local_path()` принимает как полный, так и shell-съеденный вариант WSL UNC-пути
  (`\\wsl.localhost\\Ubuntu\\...` и `\wsl.localhost\Ubuntu\...`).
- В корневом `.kilo/command/classify-article.md` добавлена команда
  `/classify-article <путь-к-статье>`.

# Progress ds_search

## 2026-09-10 — issue #92: meta_extract.py (эпик #88)

- `src/metadata/meta_extract.py`: `extract_page_meta(metadata)` — author/
  publish_date/description из `result.metadata` (crawl4ai уже парсит
  og:*/article:*/name=description|author из HTML head). Приоритет:
  og:*/article:* > обычный meta-тег > twitter:*. Без LLM.
- Интеграция: `crawler.py:_save()` передаёт `page_meta` в
  `build_ingestion_metadata(**page_meta)`.
- Тесты: `tests/test_meta_extract.py` (3). Полный прогон: 181 passed,
  1 fail не связан (test_rag_export pdf/reportlab, `mm` NameError в
  src/rag/export.py — существовал до этого issue).
- PR #98 (squash, merged), issue #92 закрыт (Closes).

## 2026-09-10 — issue #91: LLM-классификатор select-полей (эпик #88)

- `src/metadata/classify.py`: `classify(title, text, fields, domain=, dest_dir=)`
  строит промпт из активной схемы GAR (`gar_schema.field_options`/
  `category_options_for_direction`) с списком допустимых опций по
  age/target_audience/direction/category(dependent)/doc_type, зовёт LLM
  (переиспользует `src/news/llm_draft.call_llm`/`parse_llm_json`,
  провайдер/модель — `config/classify_llm.yaml`), валидирует ответ против
  схемы (невалидное значение -> None).
- Fallback-цепочка: ошибка/таймаут LLM или незакрытые LLM полем ->
  `gar_mapping.resolve_defaults` (issue #90) по домену/dest_dir; поле, не
  закрытое ни LLM, ни дефолтом, остаётся `None`. Результат содержит
  `needs_review` (True, если есть None) и `source`
  (`llm`/`llm+fallback`/`fallback`/`none`) — интеграция needs_review-статуса
  в краулер — issue #93 (не в этом issue).
- `tests/test_classify_llm.py`: 7 тестов (mock `call_llm`) — успех все
  поля, невалидное значение -> None+needs_review, fallback при ошибке LLM,
  дозаполнение частичного LLM-ответа дефолтами, без domain -> needs_review
  без fallback, парсинг реального yaml-конфига. PR #97 (squash в main),
  Closes #91.
- Полный прогон `pytest`: 178 passed, 1 fail не связан с изменением
  (`test_rag_export.py` — `NameError: mm` в reportlab-коде, эпик #43).


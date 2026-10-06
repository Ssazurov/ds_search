## 2026-10-03 -- issue #464: поиск по одному сообществу VK

- `src/search/vk_client.py`: `wall_search` принимает `owner_id` или `domain` (screen_name).
- `src/search/vk_search.py`: `parse_vk_community` (URL/`club123`/`-123`/screen_name) и `vk_community_search` (wall.search, только посты сообщества).
- `src/discovery/run_search.py`: параметр `vk_community`; если задан — домены и общий поиск игнорируются, ошибка VK -> статус `failed`.
- `ui/search_tab.py`: поле «Сообщество VK (необязательно)».
- Тесты: `tests/test_vk_search.py` (22 passed вместе с test_run_search). PR #471, контейнер `ds-search` пересобран.

## 2026-10-02 -- issue #447: trailing пробелы в markdown таблицах

- **Проблема**: `html2text` добавляет trailing пробелы после pipe-символов в таблицах (`|  \n` вместо `|\n`), что ломает рендеринг markdown таблиц на сайте.
- **Решение**: `src/crawler/filters.py` — добавлена функция `_clean_markdown_tables()` для удаления trailing пробелов после `|` через regex `r'\|\s+$'` (multiline mode). Применяется ко всем результатам `AdaptiveMarkdownGenerator`: `raw_markdown`, `fit_markdown`, `references_markdown`.
- **Тест**: `tests/test_crawler_filters.py::test_adaptive_generator_cleans_table_trailing_spaces` — проверяет корректность очистки таблиц с кириллицей.
- **Проверка**: `pytest tests/test_crawler_filters.py -v` проходит, `git diff --check` — нет whitespace ошибок, контейнер `ds-search` пересобран.
- PR #450 (Closes #447).

## 2026-10-02 -- issue #445: колонка md без ссылки при контейнерном content_path

- `ui/documents_tab.py`: `_file_uri`/`_static_uri` резолвят путь через `resolve_content_path` (`src/gar_ingest/paths.py`, issue #400) вместо голого `Path(p).resolve()` — если записанный `content_path` контейнерный (`/app/data/...`) или из другого окружения, ищется файл рядом с sidecar `.json` по тому же stem (`.md`/`.pdf`). Раньше `relative_to(ROOT)` падал → колонка `md` оставалась пустой при живом файле на диске. Без миграции данных.

## 2026-10-01 -- issue #438: статус digest_only для статьи-источника

- `ui/documents_tab.py`: новый статус строки `digest_only` — отдельная иконка `📑 только пересказ` (`_STATUS_CELL`, `_STATUS_ORDER`), не путается с `pending/error/loaded`. Выставляется функцией `_apply_digest_only_status(rows, derived)`: `doc_type=article`, нет `gar_document_id`, по `source_url` в `items_by_source_urls` есть запись со `status=published` (`format` news или digest), и флаг `digest_only_dismissed` не стоит. Вызывается в `render()` сразу после сборки `rows`, **до** `_apply_filters` (нужно для сортировки/счётчиков) — `derived` считается один раз на все строки и переиспользуется ниже для бейджа «Производные» (дублирующий запрос убран).
- `_scan_raw()`: читает `digest_only_dismissed` из sidecar `.json` в строку.
- Ручной сброс: кнопка «♻️ Снять digest_only (догрузить полный текст)» в карточке действий (видна при выборе одного документа со статусом `digest_only`) — пишет `digest_only_dismissed: true` через `_update_document_metadata`.
- Фильтр «Тип документа» (доступен в #439) и колонка `В GAR`/`_STATUS_FILTER` пока digest_only не знают — вне скоупа #438.
- `tests/test_documents_tab.py`: 7 новых тестов на `_apply_digest_only_status` (срабатывание для news/digest, игнор draft/rejected, пропуск уже загруженных и не-article, уважение ручного сброса, no-op без url). `30 passed` в файле.
- Полный набор: `504 passed`, 3 падения `test_digest.py` + 1 ImportError `test_migrate_raw_folders.py` — предсуществующие (воспроизводятся на чистом `main`).

## 2026-09-30 -- issue #434: кнопка «Скачать» на «Результатах» (скачивание без перехода на «Загрузку»)

- **`ui/results_tab.py`**: новый хелпер `_download(rows, selected_ids, settings)` — то же ядро, что «Скачать» на вкладке «Загрузки» (`add_manual_document`: dedup по canonical_url → license gate → recrawl → sidecar), вызов через `asyncio.run`, `direction`/`category` берутся из `suggested_direction`/`suggested_category` (fallback на `category`). Статусы `downloading` → `downloaded` / `error`, промежуточный `queued` **не** выставляется (решение по issue). Маппинг: `added`→`downloaded`+`скачано`, `duplicate`→`downloaded`+`дублей` (в деталях `doc_id`), `license_pending`/`license_denied`/`failed`→`error` с причиной. Батч не прерывается на первой ошибке (`except Exception` + `contextlib.suppress` на повторную смену статуса), `st.spinner` на весь батч, сводный `notify.report("Скачано: N из M", {"скачано", "дублей", "ошибок"}, errors)`, затем `st.rerun()`.
- **Ряд действий**: `action_row(6→7, "results")`, порядок `Одобрить | Отклонить | Удалить | В очередь загрузки | Скачать | В пересказ | В новости`; новая кнопка `key="results_download"` (b5), «В пересказ» → b6, «В новости» → b7.
- **`tests/test_results_tab_download.py`** (новый, 9 тестов): успех→`downloaded`, отсутствие `queued` в цепочке, `duplicate`→`downloaded`+`doc_id` в отчёте, параметризация `license_denied`/`license_pending`/`failed`→`error`, непрерывание батча при исключении, маппинг `suggested_direction`/`category`, сбой смены статуса не рвёт батч. Фейки `GarDiscoveryClient`/`add_manual_document`/`st.spinner`/`st.rerun`/`notify.report`.
- **`tests/test_results_tab_actions.py`**: `test_action_row_has_six_columns` → `..._seven_columns`, `test_button_order` (b5=Скачать, b6=В пересказ, b7=В новости) + 2 новых теста (кнопка зовёт `add_manual_document` и `_download`; хелпер держит цепочку статусов, не ставит `queued`, не рвёт батч).
- **`tests/test_no_bare_messages.py`**: номер строки `ui/results_tab.py:110→157` (сдвиг от нового хелпера).
- **Проверка**: 19 тестов затронутой зоны + полный набор `497 passed`; падающие `tests/test_digest.py` (3) и `tests/test_migrate_raw_folders.py` (ImportError) — предсуществующие, воспроизводятся на чистом `main`. Контейнер `ds-search` пересобран.

## 2026-09-30 -- issue #432: «В пересказ» отдельной кнопкой на «Документах»

- `ui/documents_tab.py`: ряд действий 6→7 (`action_row(7, "documents")`, `b1..b7`); удалён `format_selector("documents_news_fmt")` и импорт `format_selector`; новая кнопка `doc_to_digest_btn` «В пересказ (N)» → `_to_news_batch(with_url, fmt="digest")`, `doc_to_news_btn` переведён в `b7` и вызывает `fmt="news"`; `Вернуть из архива` → `Из архива`.
- Тесты: `tests/test_documents_tab_actions.py` (6 охранных проверок порядка/подписей/форматов) + поведенческий `test_to_news_batch_passes_digest_format`. В контейнере `44 passed` (`test_documents_tab.py`, `test_documents_tab_actions.py`, `test_digest_ui.py`, `test_no_bare_messages.py`).

## 2026-09-30 -- issue #430: «В пересказ» отдельной кнопкой на «Результатах», короткие подписи

- **`ui/results_tab.py`**: убран вызов `format_selector` (`st.radio("Формат")`, висел над рядом кнопок и читался как фильтр, а формат не был виден после нажатия). Вместо него две кнопки: **«В пересказ»** (`key="results_to_digest"`, `fmt="digest"`, `help` про чеклист — смысл, который раньше жил на радио) и **«В новости»** (`key="results_to_news"`, `fmt="news"`, поведение не изменилось).
- **Порядок кнопок** (было 5 колонок → стало 6, `action_row(6, "results")`): `Одобрить | Отклонить | Удалить | В очередь загрузки | В пересказ | В новости`. «Удалить выбранные» переехала с 4-й позиции на 3-ю — в блок терминальных статусных действий.
- **Подписи** статусных действий укорочены: «Одобрить выбранные» → «Одобрить», «Отклонить выбранные» → «Отклонить», «Удалить выбранные» → «Удалить». Контекст даёт счётчик `Выбрано: N` над рядом.
- **Рефакторинг**: общая логика генерации вынесена в `_to_news(rows, selected_ids, settings, fmt)` вместо двух копий по 30 строк (спиннер → `add_articles_as_news` → `summarize` → перевод `finalized_ids` в `in_news` с толерантностью к сбою API → `notify.report`).
- **`tests/test_results_tab_actions.py`** (новый, 6 тестов): охранный тест на порядок кнопок, число колонок, короткие подписи, отсутствие `format_selector`, разные key/format у двух кнопок и перенос `help` про чеклист.
- **`tests/test_no_bare_messages.py`**: обновлены номера строк в `ALLOWED` — `ui/results_tab.py:73→110` (сдвиг от рефакторинга) и три устаревших записи `ui/news_tab.py` (336/381/422 → 368/414/455), из-за которых охранный тест падал ещё до этой задачи.

## 2026-09-30 -- issue #427: отзыв (revoke) корпусных документов после публикации digest

- **Backend `src/gar_ingest/documents.py`**: добавлена `revoke_document(doc_id: int)` — отзывает корпусный документ из GAR после публикации пересказа. Сначала пытается удалить (DELETE `/documents/{gar_document_id}`), при 403 (нет прав) — архивирует (PATCH `archived=true`). Обновляет sidecar: `content_status=revoked`, `gar_document_id=None`.
- **DB `src/news/db.py`**: добавлена `has_published_digest(source_url: str) -> bool` — проверяет наличие опубликованного digest для source_url.
- **UI `ui/documents_tab.py`**: кнопка "Снять полный текст" — показывается для одного выбранного документа при наличии published digest. Диалог подтверждения перед отзывом, обновление таблицы после операции.
- **Тесты `tests/test_revoke_document.py`**: 5 тестов покрывают сценарии: успешное удаление (DELETE 204), архивирование при 403, обработка 404, ошибки GAR, обновление sidecar.
- **Проверка**: все тесты проходят, container `ds-search` rebuilt.
- PR #429 (Closes #427).

## 2026-09-30 -- issue #422: массовая переработка старых статей в пересказы

- **`src/news/bulk_digest.py`**: переводит ранее загруженные статьи корпуса (`data/raw/<domain>/*.json`, `doc_type=article`, уже с `gar_document_id` — опубликованы в GAR) в черновики `news_items(format=digest)` через `generate_draft(fmt='digest', autoclassify=True)` (переиспользует пайплайн #420/#421), без повторного скачивания.
- **Исключение доменов**: `config/digest_bulk.yaml` (`downsideup.org`, `miloserdie.ru`, `pravmir.ru` — решение эпика #419, для них остаются полные тексты).
- **Идемпотентность**: дедуп по `source_url`, как в основном news-пайплайне.
- **dry-run** (счёт кандидатов без LLM/записи) и **limit** (максимум статей за прогон, остаток — в следующий раз) + `progress_cb`.
- **CLI** `scripts/bulk_digest.py` (`--dry-run`, `--limit`), **кнопка** «Переработать в пересказы (массово)» на вкладке «Новости».
- **Не входит**: явное действие «снять полный текст» (revoke оригинала-корпуса после публикации digest) — отдельная задача, для корпусных документов пока нет revoke-клиента (только для news_items).
- **Тесты**: `tests/test_bulk_digest.py` (11 шт.) — исключение доменов, doc_type-фильтр, "не опубликовано в GAR", dry-run, идемпотентность, not_relevant, ошибка LLM не роняет прогон, limit, progress_cb, конфиг.
- PR #426 (Closes #422).

## 2026-09-30 -- issue #393: сквозная проверка Поиск → Новости → Сайт

- **Документация цепочки**: создан `docs/workflows/search-to-site-pipeline.md` — полное описание этапов от поиска до публикации на сайте с артефактами, статусами и типичными сбоями каждого этапа.
- **Чек-лист**: создан `docs/workflows/search-to-site-checklist.md` — пошаговая инструкция для ручной проверки всей цепочки с командами и ожидаемыми результатами.
- **Smoke-скрипт**: `docs/workflows/smoke_search_to_site.sh` — автоматизированная проверка доступности сервисов и наличия данных на каждом этапе (окружение, GAR API, discovered_sources, news_items, GAR doc_type=news, ds-site прокси, UI).
- **Этапы цепочки**:
  1. Поиск → `discovered_sources` (status=new)
  2. Одобрение → `news_items` (status=draft)
  3. Публикация → GAR (doc_type=news, gar_document_id)
  4. Индексация → ds_ingestion (Docling/векторизация)
  5. Сайт → ds-site `/news` (прокси `/api/gar/documents`)
- **Диагностика**: каждый этап документирован с типичными сбоями и способами их проверки (curl-команды, SQL-запросы, логи Docker).
- **Проверка**: `bash docs/workflows/smoke_search_to_site.sh` (требует GAR_API_KEY в окружении).

## 2026-09-30 -- issue #402: backfill нормализации доменов в GAR

- **Создан `scripts/backfill_gar_domain.py`**: скрипт находит документы с `www.` префиксом в `source_domain` и обновляет их через `PATCH /ingestion/documents/{id}`. Поддерживает dry-run режим (по умолчанию) и `--apply` для применения изменений.
- **Миграция выполнена**: обработано 45 документов в GAR, убран `www.` префикс у всех доменов (www.7ya.ru → 7ya.ru, www.downsyndrome.ru → downsyndrome.ru и т.д.).
- **Ручное исправление**: документ e3a803b6 (www.sonoticiaboa.com.br) имел невалидное значение `direction='news'` — очищено поле direction, обновлён домен.
- **Результат**: 0 документов с `www.` префиксом в GAR, все домены нормализованы согласно изменениям в #400.
- **Проверка**: `GAR_API_KEY=... python3 scripts/backfill_gar_domain.py` (dry-run), `--apply` для применения.
- PR #401 (Closes #402).

## 2026-09-30 -- issue #395: strip_site_suffix в _save_rejected + миграция raw-папок

- **`_save_rejected`** теперь применяет `strip_site_suffix()` к title (issue #347), как и `_save()`. Ранее отклонённые документы сохраняли title "как есть" с суффиксом сайта.
- **`GarRegistryStore.put()`** исправлен: исключает `domain` из полей перед PUT-запросом (было `TypeError: got multiple values for argument 'domain'`).
- **`scripts/migrate_raw_folders.py`**: новый скрипт для миграции файлов из нестандартных папок (`manual/`, `downsideup/`, `family_support/`, `ПОДДЕРЖКА СЕМЬИ/`, `basic/`) в папки доменов (`data/raw/<domain>/`). Обновляет `content_path` в JSON. Поддерживает `--dry-run`.
- **Миграция выполнена**: 120+ файлов перенесено из `data/raw/manual/`, `data/raw/downsideup/`, `data/raw/family_support/`, `data/raw/ПОДДЕРЖКА СЕМЬИ/`, `data/raw/basic/` в соответствующие папки доменов.
- **Тест**: `test_save_rejected_applies_strip_site_suffix` — проверяет применение `strip_site_suffix` в `_save_rejected`.
- **Проверка**: `pytest tests/test_crawler_recrawl_overrides.py tests/test_manual_add.py tests/test_meta_extract.py tests/test_title_attribution.py` — 27 passed. Полный набор: 413 passed.
- PR #401 (Closes #395, #396, #400).
- **Доработка ревью #401**: `data/` в .gitignore — корпус не версионируется (источник истины GAR); 17 случайно отслеживаемых файлов `data/raw/downsideup/` удалены из индекса (`git rm --cached`). `migrate_raw_folders.py` сохраняет префикс content_path (host// app) и переносит `.pdf`. Новый `src/gar_ingest/paths.py::resolve_content_path` — fallback на файл рядом с sidecar .json (host/`/app` пути). `config/categories.yaml` откатан (не относится к задаче). 416 tests passed.
- **Слияние www-дублей (#400)**: `norm_domain()` (slug.py) — каноничный домен без `www.`; применён в `manual_add` и `download_single`. `scripts/merge_www_folders.py` свёл `www.pravmir.ru/inva.news/medanta.org/miloserdie.ru` к доменам из Источников, `source_domain` нормализован, 1 дубль удалён. Все 150 saved-документов резолвятся. `bb85a3e502694934` (downsideup.org/cifry-i-fakty) перекачан. 417 tests.
- **Папка = домен везде**: `manual_add._resolve_source` и `crawler.py` (recrawl/CLI) использовали `cfg.name` (`downsideup`), теперь `cfg.domain` (`downsideup.org`); тест `test_resolve_source_domain_dir.py`. Перекачанный doc bb85… лежит в `downsideup.org/`.

## 2026-09-29 -- issue #372: охранный тест и документация единого вывода сообщений

- Создан охранный тест `tests/test_no_bare_messages.py`: проверяет отсутствие прямых вызовов `st.success/error/warning/info` в `ui/*.py` (кроме `notify.py`).
- Allowlist с явным обоснованием для каждого исключения (пустые состояния, inline-подсказки, статусы фоновых процессов).
- Создана документация `docs/ui-messages.md`: правила использования `notify.report/report_batch/toast`, цвета по исходам, примеры кода.
- Все подзадачи эпика #366 завершены: поиск (#367), документы (#369), результаты+загрузка (#370), остальные вкладки (#371), охранный тест+документация (#372).
- Проверка: `pytest tests/test_no_bare_messages.py` — passed. Эпик #366 готов к закрытию.

## 2026-09-29 -- issue #370: вкладки «Результаты» и «Загрузка» — единый вывод сообщений

- Перевод всех результатов операций на `notify.report` / `notify.report_batch` в `ui/results_tab.py` и `ui/upload_tab.py`.
- **Результаты**: кнопки «Одобрить», «Отклонить», «В очередь», «Удалить», «В новости» (с детальной статистикой черновиков/дублей).
- **Загрузка**: скачивание из очереди, добавление по ссылке, ручная загрузка файлов.
- Оставлены `st.info` только для информационных состояний (пустая очередь, нет результатов).
- Проверка: PR #376 смержен, синтаксис Python OK, `git diff --check` чист, контейнер ds-search пересобран.

## 2026-09-29 -- issue #369: вкладка «Документы» — сообщения через notify.report_batch

- Заменены все `st.success/st.error/st.warning/st.info` на `notify.report` / `notify.report_batch` в `ui/documents_tab.py` (10 мест).
- Добавлена функция `_row_label(row)` для отображения названия документа вместо doc_id в ошибках.
- Сообщения теперь переживают `st.rerun()` и держатся вверху вкладки до закрытия ✕.
- Частичная неудача показывается жёлтым, с подробностями в раскрываемом блоке.
- Проверка: PR #375 смержен, код импортируется без ошибок. Требуется ручная проверка в UI для проверки визуального отображения сообщений.

## 2026-09-29 -- issue #360: backfill даты источника для старых записей

- `run_probe_stage` получил параметр `only_missing_date: bool = False` (issue #355 ветка): при `True` пропускает находки с заполненной `source_published_at`, не обновляет `relevance_score` (режим «только дата»), добавлена пауза 0.5с между запросами.
- CLI: `python -m src.discovery.probe --only-missing-date --status new` (argparse, аргументы `--only-missing-date`/`--status`). Логи: scored/thin/error/skipped/updated.
- Счётчики: `skipped` (пропущено с датой), `updated` (реально обновлено в БД).
- Тест `test_run_probe_stage_only_missing_date_skips_filled`: probe_source не вызывается для находок с датой, relevance_score не записывается в backfill режиме.
- Проверка: `pytest tests/test_probe.py -q` — 8 passed.
- Примечание: команда для backfill старых записей без даты — `.venv/bin/python -m src.discovery.probe --only-missing-date --status new`, провайдер → probe fallback (ADR-002), дата не перезаписывается.

## 2026-09-28 -- issue #340: paragraph breaks (single_line_break=False)

- `AdaptiveMarkdownGenerator` передаёт html2text `single_line_break=False` (crawl4ai по умолчанию True -> абзацы `<p>` склеивались одиночным `\n`). Явные `html2text_options` вызывающего имеют приоритет.
- `fix_missing_newlines` удалена (regex-костыль давал +2 переноса на статью и ломал юниты: "кВт" -> "к\nВт").
- Проверка: `pytest tests/test_crawler_filters.py`; foma.ru/v-ozhidanii-dauna.html: 151 разрыв абзацев. Ранее скачанные документы нужно перекачать (reload на вкладке Документы).
- reload: перекачка источника с таймаутом 30 с (опрос 5 с), ошибки sidecar/source_url поднимаются как GarPublishError, контент подменяется атомарно.

## 2026-09-28 -- author link in document reload metadata

- `extract_author_from_markdown` теперь сохраняет markdown-ссылку автора целиком,
  например `[КАПЛАН Виталий](https://foma.ru/authors/kaplan-vitalij)`, вместо
  удаления URL и сохранения только ФИО.
- Добавлен регрессионный тест для строки `Автор:` с ссылкой и fallback
  `article:author`.
- Проверка: `pytest tests/test_meta_extract.py`.

## 2026-09-29 — #388 Ручная загрузка: папка по домену
`add_manual_document` пишет в `data/raw/<domain>/`, имя = slug заголовка (`src/crawler/slug.py`), dedup по source_url. UI: убраны поля папки/имени. Тесты 402 passed.

## 2026-09-29 -- issue #392: устойчивость «В новости» при сбое смены статуса

- Обёрнут вызов `update_discovered_source` в try-except (ui/results_tab.py:146-149).
- Ошибки смены статуса собираются в `status_update_errors` и передаются в `notify.report` через `all_errors`.
- Сообщение "⚠️ Не удалось обновить статус (черновики сохранены)" добавлено в детали.
- Черновики не теряются при сбое API, дедупликация работает на уровне `add_single_url` (существующая логика в ui/news_add.py).
- Тесты: `test_to_news_survives_status_update_failure`, `test_to_news_dedup_prevents_double_draft`, `test_status_update_partial_failure`.
- Проверка: `pytest tests/test_results_tab_to_news.py -v` — 3 passed. Commit c87261b, issue #392 закрыт.

---

## 2026-09-30: Raw folder backfill migration (#400)

**Проблема:** Файлы из `links_items/` находились не в правильных доменных папках согласно их `source_domain`.

**Реализация:**
- Создан `scripts/migrate_raw_folders.py` для переноса файлов в правильные папки по домену
- Добавлена поддержка IDN (кириллических) доменов через транслитерацию всего домена:
  - `город-надежды.рф` → `gorod-nadezhdy-rf/`
  - `дети-лучики.рф` → `deti-luchiki-rf/`
  - `солнечные-дети.рф` → `solnechnye-deti-rf/`
- Скрипт умеет:
  - Резолвить правильную папку через `SOURCES` или `domain_dirname()`
  - Обновлять `content_path` в JSON после переноса
  - Пропускать внутренние файлы (`source_domain=ds_search`)
  - Работать в режиме `--dry-run`

**Результат:**
- Перенесено 126 файлов из `links_items/` в правильные доменные папки
- Добавлены unit-тесты (7 passed)
- Повторный запуск подтверждает: `✅ Все файлы уже в правильных папках`

**Верификация:** PR #405 merged, контейнер ds-search пересобран (кэш использован, образ готов).

## 2026-09-30 -- issue #390: Верификация constraint in_news на stage

- **Задача**: Проверить stage-окружение после миграции z4d5e6f7a8b9 (добавлен статус `in_news` в constraint БД).
- **Проверки**:
  - Миграция применена: ревизия z4d5e6f7a8b9 (head) в docker/systemd
  - Schemas синхронизированы: `DISCOVERED_SOURCE_STATUSES` включает `in_news`
  - Guard-тест `test_discovered_source_statuses_guard.py` PASSED
  - Прямой тест constraint через БД: `UPDATE discovered_sources SET status='in_news'` выполнен без ошибок (транзакция с ROLLBACK на документе de5883d0-c06f-407c-bdd7-ad2c3b5b131e)
  - В production БД уже существуют записи со статусом `in_news`
- **Acceptance criteria**: ✅ все выполнены
  - Constraint принимает статус `in_news` без ошибок
  - Docker/systemd на одной ревизии и БД
- **Результат**: Issue #390 закрыт. Constraint работает корректно на всех уровнях.

## 2026-09-30 -- issue #415: Новости — направление/категория, отзыв из GAR при отклонении

- **Форма новости** (`ui/news_tab.py`): «Направление»/«Категория» из живой схемы GAR (ADR-013, как в «Документах»); `db.EDITABLE_FIELDS` += direction, category; явные значения приоритетнее LLM в `publish.build_metadata`.
- **Дата**: подпись «Дата публикации: dd.mm.YYYY HH:MM» (в БД пишется ISO, как раньше).
- **Fix**: `notify.report("news", ...)` → `notify.report(...)` (news_tab ×12, sources_tab ×1) — TypeError при публикации.
- **«В GAR»**: 🟥 для статуса rejected.
- **Отклонение** (`_reject_item`): при `gar_document_id` сначала `revoke_news_item`; ошибка отзыва → статус не меняется; успех → rejected, gar_document_id очищен.
- **Верификация**: py_compile OK, контейнер ds-search пересобран (кэш использован).

## 2026-09-30 -- issue #417: кнопки действий под таблицами — вправо, равные промежутки

- **Хелпер `action_row(n, key)`**: добавлен в `ui/table_utils.py` — создаёт ряд из n кнопок с CSS-классом `st-key-actions_{key}`.
- **CSS `.st-key-actions_*`** в `ui/app.py`: `justify-content: flex-end`, `gap: 0.5rem`, `flex: 0 0 auto`, `width: auto` — прижимает кнопки вправо с равными малыми промежутками, адаптивная упаковка.
- **Применено на вкладках**:
  - Документы: 6 кнопок (Загрузить в GAR, Удалить из GAR, Одобрить, Отклонить, Перезагрузить, Удалить)
  - Новости: 3+4 кнопки (Опубликовать/Отклонить/Удалить, Сохранить/Опубликовать/Отменить/Удалить)
  - Результаты: 5 кнопок (Одобрить, Отклонить, В очередь, Удалить, В новости)
- **Проверка**: UI localhost:8501 — кнопки справа, равные промежутки между ними.
- Container ds-search rebuilt, UI готов к проверке.
- PR #418, Closes #417.


## Архив

- Записи 2026-09-30 (ds_search#420, #423 и последующие) вынесены в [CURRENT_STATUS-2026-09-30_part2.md](docs/archive/current-status/CURRENT_STATUS-2026-09-30_part2.md)
- Записи 2026-09-25 — 2026-09-27 вынесены в [CURRENT_STATUS-2026-09-25_2026-09-27.md](docs/archive/current-status/CURRENT_STATUS-2026-09-25_2026-09-27.md)

## 2026-10-02 -- issue #451: миграция существующих markdown файлов (trailing пробелы в таблицах)

- **Проблема**: исправление #447 (PR #450) применялось только при новом скрапинге. Уже загруженные статьи содержали битые таблицы с trailing пробелами.
- **Решение**: `scripts/migrate_fix_tables.py` — применяет `_clean_markdown_tables()` ко всем `data/raw/**/*.md`. Dry-run режим для preview, обновляет `modified_at` в sidecar `.json`, идемпотентный (повторный запуск не меняет уже исправленные файлы).
- **Результаты миграции**: обработано 347 .md файлов, исправлено 4, пропущено 343, ошибок 0.
- **Исправленные файлы**:
  - `t-l.ru/f32f72e2b79208ee.md`
  - `downsideup.org/4087a890fd025a1c.md`
  - `downsideup.org/07233a95bbd97df5.md` (статья 28768ef3-d5e1-444f-b2fa-c9355002c388)
  - `downsideup.org/pomoshch-roditelyam-v-prinyatii-diagnoza-rebenka-put-k-normalizatsii.md`
- **Проверка**: миграция применена локально, `data/` в `.gitignore` — коммитится только скрипт. Исправленные файлы используются сайтом сразу, контейнер перезагружать не нужно.
- PR #452 (Closes #451).

## 2026-10-06 — #569 resolve_author
- `src/metadata/author_resolver.py`: author = meta/шапка/тело → HTML (JSON-LD, «Автор:») → LLM (только если пусто, имя должно быть в тексте) → `config/site_authors.yaml` → site_name реестра → og:site_name. Подключён в crawler._save и discovery/download. Регулярка «Автор:» в md терпит `_*`, роль после « - » отрезается.

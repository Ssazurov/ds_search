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

## 2026-09-25 -- issue #292: ссылки на локальные md/json черновики в таблице Документов

- Добавлены колонки «MD» и «JSON» с `file://` ссылками на `content_path` (md/pdf) и `doc_json_path` (sidecar) через `st.column_config.LinkColumn` с material-иконками.
- Ссылки открываются в приложении по умолчанию через браузер (не рендерятся в браузере).
- Только вкладка Документы — для Материалов нет прямой связи `gar_document_id → content_path` без доп. поиска по `*.ingested.json`.
- Проверка: `py_compile` OK, коммит db9337b.
- ADR не требуется (UI-правка без изменения контракта).
- Пересборка не нужна (не влияет на функциональность в контейнере, только UI Streamlit).

## 2026-09-25 -- issue #290 (Epic): удаление lifecycle_stage (ADR-0022, амендмент ADR-0002)

- Поле `lifecycle_stage` полностью убрано из кода ds_search: `src/metadata/profile.py` (`build_ingestion_metadata`, `LIFECYCLE_STAGES`), `src/metadata/schema.py` (`REQUIRED_FIELDS`, словари), `config/categories.yaml`, `src/crawler/config.py`/`crawler.py`, `src/discovery/download.py`, `src/news/publish.py`, `ui/search_tab.py`/`upload_tab.py`/`documents_tab.py` (поле/фильтр/форма), `src/rag/sessions.py` (`SessionTopic` — теперь единственный дискриминатор `category`), `src/rag/patient_profile.py` (retrieval-фильтр только по `comorbidity_tags`).
- Тесты обновлены под новый контракт (test_metadata_profile/test_news_publish/test_download/test_rag_sessions/test_patient_profile/test_rag_response_modes.py). Полный прогон: **314 passed**.
- ADR: `ds/docs/adr/0022-remove-lifecycle-stage.md` (амендмент root ADR-0002) + запись в `ds/docs/decisions.md` и `ds_search/docs/decisions.md`.
- Не тронуто (вне скоупа эпика): поле в самой GAR-админке (удаляется вручную), `ds_ingestion` (`gar_client/metadata_fields.py`, `adapter/pipeline.py` — маппинг известных полей, отдельная задача при необходимости), исторические значения в старых sidecar `.json`.
- Пересборка не требуется отдельно от PR-мержа (см. ниже после коммита/деплоя).

## 2026-09-25 -- issue #286 (запушено) + #288: метаданные на вкладке Документы

- **#286** (PR #287): форма редактирования direction/category/lifecycle_stage/age/needs_review на вкладке Документы (`ui/documents_tab.py::_render_metadata_form`). direction/category — из живой схемы GAR (`src/metadata/gar_schema.py`, только активные controlled-опции), не из локальных констант. Для уже загруженных в GAR документов правка уходит и в sidecar `.json`, и через `PATCH /documents/{id}` (`_patch_gar_metadata`, `GarIngestClient.patch_document_metadata`). `publish_permission` теперь проставляется при скачивании из `license_result.publish_permission` (`src/crawler/crawler.py`, `src/discovery/download.py`) — раньше поле не заполнялось. Таблица уже локализовала direction/category через существующий `ui/table_utils.localize()`/`label_of()` (кэш словаря из GAR, обновляется кнопкой на вкладке Справочники) — отдельный маппинг не потребовался. Код был реализован в прошлой сессии, но не закоммичен — в этой сессии только commit/PR/merge.
- **#288** (PR #289): при отметке документов галочкой форма выше предзаполняется direction/category, если значение одно на всех выбранных и валидно в текущей схеме GAR; при разных значениях в выборке — пусто ("не выбрано"), чтобы не перезаписать документы одним значением по ошибке. Реализовано через `st.session_state["_batch_meta_sel_key"]` (сигнатура выбранных `doc_id`) — сброс `batch_direction`/`batch_category` в session_state только при смене состава выборки, ручной выбор пользователя внутри одной и той же выборки не затирается.
- Проверка: `py_compile` обоих файлов OK; `pytest tests/test_gar_ingest_documents.py tests/test_gar_schema.py tests/test_metadata_profile.py tests/test_metadata_schema.py` — 20 passed. ADR не требовался (без изменения контракта/схемы, только UI+инициализация уже существующего поля).
- Пересборка ds-search дважды (после #287 и после #289): `~/build.log` — нет `failed to solve`, все шаги (pip/apt/chromium/node) `CACHED`.

_Разделы 2026-09-18…2026-09-24 перенесены в [docs/archive/current-status/CURRENT_STATUS-2026-09-18_2026-09-24.md](docs/archive/current-status/CURRENT_STATUS-2026-09-18_2026-09-24.md)._

## 2026-09-20 — #228 публикация внешнего сайта из контейнера ds-search
- Dockerfile: node 22.23.1, git, gh; runner.py: `DS_SITE_GAR_URL` → GAR_URL для сборки в docker.
- gar-deploy compose: том ds_site, конфиг gh, DS_SITE_DIR, git credential helper через gh.
- Проверка: контейнер пересобран, node/git/gh/gh auth есть, dry-run из контейнера: exit 0 (сборка + проверка секретов). Реальная публикация в gh-pages не гонялась.

## 2026-09-20 — #234 Источники/домены: master-detail
- ui/sources_tab.py: список доменов слева (фильтры, поиск, пагинация 10/20/50), форма справа (Сохранить/Отменить/Удалить); русские подписи статусов (значения в licenses.yaml не менялись); баннер pending убран.
- tests/test_sources_tab_rows.py; проверка: pytest 12 passed.


## 2026-09-23 — «Параметры поиска»: необязательный период дат (от/до) (#247, PR #248)
- `ui/search_tab.py::_date_range()`: два date_input + time_input «От»/«До» (необязательно, очистка поля убирает границу). «До» по умолчанию — текущая дата и время (через `session_state.setdefault`). Предупреждение, если «От» позже «До».
- `src/search/base.py::SearchProvider.search` — `date_from`/`date_to: datetime | None` в интерфейсе (точность — день).
- `src/search/chain.py::SearchProviderChain.search` — прокидывает даты только если заданы (`extra` строится по не-None).
- `src/search/firecrawl.py` — `tbs=cdr:{from}:{to}` (Firecrawl date range); `brave.py` — `freshness`-параметр; `tavily.py` — `start_date`/`end_date`.
- `src/discovery/run_search.py::_search`/`run_search` — `date_from`/`date_to` прокидываются в цепочку (сайты-домены получают даты каждый).
- Тест: `tests/test_search_date_range.py` (2: даты доходят до провайдера только когда заданы; `chain` не шлёт None-границы).
- Проверка: pytest 5 passed (test_search_date_range + test_run_search_domains); контейнер ds-search пересобран (CACHED, без `failed to solve`), код в контейнере подтверждён по `ui/search_tab.py` (строки 57/59/61/63/109/123).

## 2026-09-23 — «Параметры поиска»: необязательный перечень доменов
- `ui/search_tab.py`: поле «Домены (необязательно)» (запятая/перенос), сохраняется в пресет.
- `src/discovery/run_search.py`: `run_search(..., domains=)` → `normalize_domains` (без схемы/www/пути), запрос дополняется `(site:a OR site:b)`, находки жёстко фильтруются по хосту (домен + поддомены). Без проверки разрешений публикации. Тесты: `tests/test_run_search_domains.py`, всего 292 passed.
- Доработка (2026-09-23, позже): мультивыбор «Домены из источников» (домены вкладки «Источники» = `licenses.yaml` ∪ `discovered_sources` без rejected, кроме `status=deny`; счётчики находок, кэш счётчиков 60 с, issue #243) + текстовое поле «Новые домены»; в пресет — оба (`domains_selected`, `domains`). Поиск с доменами теперь отдельным запросом `query site:домен` на каждый домен (один `(site:a OR site:b)` работал ненадёжно) + фильтр по хосту, лимит делится между доменами; токены без точки («и») игнорируются. Стоимость: 1 поиск на домен. 294 passed, контейнер ds-search пересобран.

- 2026-09-24 (#263, ADR-0021): клиент реестра источников (GarDiscoveryClient.*_source_registry_*), src/license/registry_store.py (GarRegistryStore: GAR + кэш data/source_registry_cache.json, при недоступности GAR — кэш, иначе pending_manual_review), check_license(registry_store=...). Переходный флаг SOURCE_REGISTRY_BACKEND=yaml|gar (по умолчанию yaml, поведение не изменено; gar включаем при миграции #265). Проверено: pytest tests/test_registry_store.py + test_license_checker.py (17 passed). Пересборка контейнера не нужна (по умолчанию поведение прежнее).

- ds_search#264: потребители реестра (sources_tab, search_tab, backfill_license) через фасад src/license/registry_store (load_registry/save_entry/delete_entry); backend по SOURCE_REGISTRY_BACKEND (yaml по умолчанию). checker/crawler/manual_add/news/site_publish уже идут через check_license. Тесты: 21 passed. ds ADR-0021.

- ds_search#265: реестр мигрирован в GAR (20 доменов, scripts/migrate_registry_to_gar.py, идемпотентно); SOURCE_REGISTRY_BACKEND по умолчанию gar; config/licenses.yaml удалён; тесты герметичны (yaml через conftest). GAR пересобран из main, alembic r6e7f8a9b0c1 применён. ds ADR-0021.

- 2026-09-24 (#278, уточнение после закрытия): жалоба «сортировка сбрасывается» — не баг сохранения (popover ⚙ Колонки → выбор колонки+Сохранить в ui_prefs.json работает исправно), а путаница с нативным кликом по заголовку st.data_editor (glide-data-grid) — тот сорт чисто клиентский, в Python не попадает и в принципе не персистится (нет API у Streamlit). Решение не требуется, документировано на будущее. Issue #278 остаётся closed.

- 2026-09-24 (#280, PR #281): вкладка Загрузка — формы «по ссылке» объединены, _render_direct_download удалён из ui/upload_tab.py. py_compile и git diff --check OK; вживую в UI проверяется после пересборки deploy-ds-search.

- 2026-09-24 (#282, PR #283): вкладка Новости переведена на table_utils (как Документы/Результаты) — компактная st.dataframe вместо N st.expander на все записи; полная форма редактирования монтируется только для выбранной строки (session_state). Пагинация db.list_news_items(limit, offset), поиск по заголовку/источнику на уровне SQL, чекбокс-колонка + массовая публикация/отклонение, фильтры в query_params (persist F5). ADR не потребовался (изменение локально в ds_search/ui). Тесты: test_news_db/test_news_manual/test_news_publish — 33 passed. PR смержен, контейнер ds-search пересобран (CACHED, без failed to solve).


## 2026-09-26: Материалы vs Документы — ADR-014 создан, эпик и подзадачи заведены

- ADR-014 (`ds_search/docs/adr/ADR-014-materialy-dokumenty-obedinenie.md`) + запись в `docs/decisions.md`.
- Эпик #294 (project #4), подзадачи #295–302 (merge rows, фильтр Локально+Сбросить,
  фильтр статуса GAR, архивация, удаление из GAR, reload из источника, PATCH title/summary,
  удаление вкладки Материалы).
- Отдельные задачи (вне эпика): #303 — старые категории отображаются как methodology,
  #304 — баг: список Категория не обновляется при смене Направления в форме редактирования.
- Код не менялся, реализация не начата.
- Ревью 2026-09-26: #295 — блокер (без merge не на чем показать GAR-only
  строки для 296-301), #302 — строго последним после ручной проверки в
  проде. GAR list_documents() в #295 — по кнопке «Обновить», не на каждый
  рендер. #299 — `delete_document()` сейчас чистит только GAR, локальный
  файл не трогает; нужна явная семантика (GAR/локально/оба) + текст
  подтверждения о необратимости. Детали — ADR-014 и комментарии в issues.

## 2026-09-26: Материалы vs Документы (анализ, исходная заметка)

**Задача (от пользователя):** перенести уникальные возможности вкладки
"Материалы" (ui/materials_tab.py) во вкладку "Документы"
(ui/documents_tab.py) и удалить "Материалы". Изменение кода НЕ начато —
только анализ. Правки контейнеров/конфигов делать только после
подтверждения пользователя.

**Ключевое отличие источников данных:**
- Документы — сканирует ФС: `data/raw/*/*.json` (+ проверка `data/clean/`).
  Статус в GAR берётся из `gar_document_id`/`ingest_error` в локальном json,
  не из самого GAR API.
- Материалы — читает GAR API напрямую (`GarIngestClient.list_documents`).

**Уникальное в Материалах (нет в Документах):**
1. Видит документы в GAR, у которых нет/удалён локальный raw-файл
2. Фильтр по статусу GAR: Активные/Архив/Все
3. Архивация/разархивация (поштучно и пакетно)
4. Полное удаление из GAR с подтверждением (Документы удаляют только
   локальные файлы, GAR не трогают — см. коммент в `_delete_files`)
5. "Перезагрузить из источника" (`reload_by_gar_id`, через ds_ingestion)
6. Редактирование title/summary одного документа с PATCH в GAR (карточка)

**Открытый вопрос перед ADR:** если объединять в один список — что делать
с документами, которые есть в GAR, но чей локальный raw-файл удалён/отсутствует
(Документы их сейчас вообще не увидят)? Решение -  объединять
local rows + GAR-документы без соответствия по gar_document_id.

**Побочная находка — осиротевшие данные:**
`data/raw/<domain>/`. Это результат скачивания через
`src/discovery/download.py` (вкладки Поиск/Результаты) ДО того, как
`DEFAULT_DATA_ROOT` был переведён на `data/raw` (сейчас
`DEFAULT_DATA_ROOT = .../data/raw`, см. download.py:47). Формат файлов
идентичен текущему (`<hash>.json`+`.md`), просто на уровень выше.
Ни в одном сэмпле нет `gar_document_id` → в GAR не загружены. Их не видит
ни Документы (сканирует только `data/raw/`), ни Материалы (GAR API).


**Следующий шаг (задача пользователя):**

спроектировать adr и создать эпик и подробные подзадачи для переноса вкладки в Документы.

## 2026-09-26 — issue #322: мелкие доработки дизайна вкладки Документы

- Кнопка **Сбросить** перемещена в строку с фильтрами (c7.button с on_click callback вместо if-блока).
- Кнопка **Обновить список из GAR** и надпись про кэш размещены после кнопки **Колонки** в одной строке (col_settings, col_gar_refresh, col_gar_info через st.columns([1, 2, 5])).
- Удалены пояснительные надписи: "Стадии raw/clean...", "Скачивание документов по URL...".
- Кнопки под таблицей прижаты к правому краю через spacer-колонку (st.columns([3, 1.2, 1, 1, 1, 1.2])).
- Проверка: git diff показывает -34/+32 строк, синтаксис корректен.
- PR #323 смержен в main, issue #322 закрыт автоматически.
- Пересборка контейнера ds-search не требуется (только UI-правки Streamlit без изменения функциональности).
в таблице в Документы - если локального файла нет, но документ загружен в gar, то в колонках ms and json ничего не писать (нет ссылки). добавить фильтры - Локально со значениями чтобы отсеять те которые есть локально или их нет или не выбрано
добавить кнопку Сбросить (фильтры)

создать отдельную задачу - разобрать документы со старыми категориями - в таблице показываются в категории methodology
также баг - выбрать галочкой статью в таблице - в форме редактирования выбрать направление - поле категории не меняется - там должны появиться категории выбранного направления


## 2026-09-26 (#295, PR TBD): Документы — merge local rows + GAR-only

- ui/documents_tab.py: \_fetch_gar_documents()\ — весь список GAR по
  кнопке «Обновить список GAR» (не на каждый рендер, ADR-014 риск 1),
  кэш в \st.session_state['gar_docs_cache']\.
- \_gar_only_rows()\ — строки для документов из GAR-кэша без
  \gar_document_id\ в локальных raw-файлах; \doc_json_path\/
  \content_path=None\ -> колонки MD/JSON пустые (_file_uri уже
  null-safe).
- Guard от падения на GAR-only строках без локального файла:
  \_delete_files\ бросает ValueError с явным текстом (полное удаление
  из GAR — #299), \_update_document_metadata\ пропускается если
  \doc_json_path is None\ (PATCH в GAR всё равно уходит).
- py_compile OK, git diff --check OK. Тестов на ui/documents_tab.py нет
  (не менялись). Живая проверка — после пересборки ds-search.

## 2026-09-26 -- issue #296: фильтр Локально + кнопка Сбросить в таблице Документов

- Добавлено поле `local: bool` в строки таблицы: `True` для локальных документов (`_scan_raw()`), `False` для GAR-only документов без локального файла (`_gar_only_rows()`).
- Фильтр «Локально» (Все/Да/Нет) добавлен в пятой колонке фильтров (`_apply_filters()`).
- Кнопка «Сбросить» очищает все пять фильтров таблицы Документов (`doc_filter_text`, `doc_filter_status`, `doc_filter_domain`, `doc_filter_direction`, `doc_filter_local`) через `st.session_state.pop()` и `st.rerun()`.
- Проверка: `py_compile` OK, `git diff --check` чисто, коммит 396db3b.
- ADR не требуется (UI-правка, продолжение ADR-014 из эпика #294).
- Пересборка: UI-правка Streamlit требует пересборки контейнера ds-search для применения изменений в проде.

## 2026-09-26 -- issue #314: recrawl_url override-параметры dest_dir/filename/direction/category

- `SourceCrawler.recrawl_url` (src/crawler/crawler.py) получил keyword-only параметры `dest_dir`, `filename`, `direction`, `category` для объединения с `download_single` (часть epic #313).
- `dest_dir` — путь относительно `self.out_dir`, валидация через новый метод `_resolve_dest_dir` (абсолютный путь или escape за пределы `self.out_dir.resolve()` → `None` + `logger.warning`, без исключения, контракт `recrawl_url` сохранён).
- `filename` — санитизируется через `discovery.download._sanitize_filename` (импорт добавлен, циклического импорта нет), используется как basename вместо `sha256(canon_url)[:16]`.
- `direction`/`category` — перекрывают `self.cfg.direction`/`self.cfg.category` только для данного вызова, не мутируют конфиг.
- Параметры протащены в `_save` и `_download_pdf`: `base_dir = self._resolve_dest_dir(dest_dir)` вместо жёсткого `self.out_dir`, `doc_id = _sanitize_filename(filename) if filename else hashlib.sha256(...)[:16]`, `direction=direction or self.cfg.direction`, `category=category or self.cfg.category` в `build_ingestion_metadata`.
- Обратная совместимость: вызовы `_save`/`_download_pdf` из `run()` (full-scan) без изменений сигнатур (4 позиционных аргумента, новые параметры по умолчанию `None`).
- Старые вызовы `recrawl_url(url)` (manual_add.py, recrawl_cli) работают без изменений (все новые параметры keyword-only с дефолтом `None`).
- Тесты: `tests/test_crawler_recrawl_overrides.py` (6 сценариев: регрессия без kwargs, filename override, dest_dir override, escape rejection, direction/category override, run() full-scan регрессия). Запускаются в Docker после пересборки.
- Проверка: `git diff --check` — чисто, `python3 -m py_compile` — синтаксис OK, сигнатура в runtime: `(self, url: str, *, dest_dir: str | None = None, filename: str | None = None, direction: str | None = None, category: str | None = None) -> dict | None`, `_resolve_dest_dir` работает корректно (валидирует относительные пути, отклоняет абсолютные/escape).
- Коммит 93e71c6, PR #319 merged в main (7186e6d).
- Пересборка ds-search: `~/build.log` — нет `failed to solve`, все шаги (pip/apt/chromium/node) `CACHED`, chromium не перекачивался.

## 2026-09-27 -- issue #111: «Удалить из GAR» не снимает галочку «В GAR»
- `_delete_from_gar_batch` (`ui/documents_tab.py`) теперь после успешного
  `client.delete_document()` сбрасывает `gar_document_id` и `ingest_error` в
  локальном sidecar `.json` через `_update_document_metadata`. Раньше документ
  удалялся из GAR, но локальный метафайл продолжал помечать его как
  загруженный, и `_scan_raw()` возвращал `status="loaded"` — галочка «В GAR»
  оставалась на месте без ручного обновления.
- Ошибка сброса локального статуса добавляется в общий `errors` — не роняем
  успешное удаление из GAR, но пользователь видит причину.
- Регрессионный тест `test_delete_from_gar_batch_clears_local_gar_flag`
  (`tests/test_documents_tab.py`): проверяет, что после удаления
  `gar_document_id` == None в sidecar и `_scan_raw()` возвращает
  `status="pending"`.
- Проверка: `pytest tests/test_documents_tab.py` — 13 passed.

## 2026-09-26 -- issue #315: integrate add_manual_document into upload tab

- **Problem**: Upload tab called `recrawl_url` directly, bypassing deduplication and license checking logic in `add_manual_document`.
- **Solution**: 
  - Extended `add_manual_document` to accept `dest_dir`, `filename`, `direction`, `category` override params (proxied to `recrawl_url` for unified crawl pipeline).
  - Updated `upload_tab.py` to use `add_manual_document` instead of direct `recrawl_url` call — now all URL downloads go through dedup/catalog filtering.
- **Files changed**: `src/crawler/manual_add.py`, `ui/upload_tab.py`, `tests/test_manual_add.py` (+test for override params).
- **Verification**: `pytest tests/test_manual_add.py` — all tests passed. Merged via PR #320.
- **Rebuild**: Container `ds-search` rebuilt via `rebuild.sh`, all layers cached (no network downloads), service up.
- 2026-09-28: issue #343 — добавлены регрессионные тесты для извлечения автора
  и `_refresh_local_content`: приоритет автора из тела, URL/отсутствующие
  данные, не-200 resolve, отсутствующий sidecar/source_url, timeout,
  смена расширения и атомарная замена контента. Проверка: 25 тестов.

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

## 2026-09-30 — ds_search#420: пересказ (digest), модель/промпт/overlap
- `news_items`: колонки `format`, `quotes`, `overlap_max_run`, `overlap_ratio` (миграция в `db.init_db`).
- `llm_draft.generate_draft(..., fmt="digest", autoclassify=...)`, `prompt_template_digest` + `max_tokens_digest`/`num_ctx_digest` в `news_llm.yaml`.
- `src/news/overlap.py`: серия ≥8 слов / доля 5-грамм >15% (цитаты исключены), лимиты цитат (≤2, ≤25 слов).
- `publish`: `doc_type=digest`, блок «Полный текст — на сайте источника», без http(s)-URL публикация запрещена.
- ADR-0024 (ds/docs/adr). Требуется активная опция `doc_type=digest` в GAR (вручную).
- Container ds-search rebuilt, UI без изменений (UI — #421). PR #<pr>, Closes #420.

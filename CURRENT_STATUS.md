## 2026-09-24 -- issue #275: UI-полировка (запоминание вкладки, название, отступ)

- `ui/app.py`:
  - **Название сайта** — `page_title` и заголовок заменены на русское «Солнечный мир (администрирование)» (см. `ds_site/app/layout.tsx`, где сайт называется «Солнечный мир»).
  - **Отступ сверху** — CSS `div.block-container { padding-top: 2.5rem !important; }` (дефолт Streamlit ~5rem, уменьшено в 2 раза на всех вкладках).
  - **Запоминание открытой вкладки**: при старте читается `?tab=<имя вкладки>` из `st.query_params` и открывается соответствующая вкладка; при переключении JS-компонент (`st.components.v1.html`) пишет имя активной вкладки в URL через `history.replaceState` — Streamlit перезапускает скрипт и восстанавливает вкладку при обновлении страницы. Имена вкладок передаются в JS как JSON-массив (кириллица кодируется через `encodeURIComponent`).
- Проверка: `py_compile ui/app.py` OK; `AppTest` рендерит без исключений, `query_params['tab']='Новости'` → вкладка «Новости» открыта (в AppTest не отслеживается активная вкладка, но логика селекта по индексу работает). JS-синхронизация проверялась вручную в браузере не была (ограничение AppTest).
- ADR не нужен (UI-полировка, без архитектурных изменений).
- **Пересборка (2026-09-24):** контейнер `deploy-ds-search` пересобран через `scripts/rebuild.sh ds-search`. Лог `~/build.log`: нет `failed to solve`, образ создан за ~3 с — все слои (pip, chromium, apt, node) взяты из кэша, перескачивающих шагов не было. В контейнере проверено: `Солнечный мир` — 3 совпадения, `block-container` — 2 (CSS `padding-top: 2.5rem !important`), `query_params` — 1, `curl localhost:8501` → HTTP 200.
- Примечание: локальная ветка `feat/275-ui-polish` и PR #276 были убраны — то же правка уже слита в `origin/main` коммитом `c4ceadf`, PR #276 закрыт как дубликат.
- **Регрессия и фикс (2026-09-24, issue #277):** коммит `c4ceadf` убрал `sys.path.insert(0, .../parents[1])` в начале `ui/app.py` → в проде `ModuleNotFoundError: No module named 'ui'` (при `streamlit run ui/app.py` в sys.path попадает только `/app/ui`, а не `/app`, нужный для `from ui import (...)`). Исправлено коммитом `ca654e6` — строка возвращена. Контейнер `ds-search` пересобран и перезапущен, проверено: `curl localhost:8501` → HTTP 200, в логах контейнера ошибок нет.
- **Баг «вкладка не запоминается» (2026-09-24), финальный фикс `c4bfbc0`:** после двух неудачных попыток починить через JS (`db58ead`, `1f1ca0d` — клики по внутреннему DOM `st.tabs()` / `data-baseweb="tab"` через `components.v1.html`, iframe/тайминги/несовпадение разметки) решено отказаться от `st.tabs()` полностью — у него в принципе нет способа задать активную вкладку программно. Заменено на `st.segmented_control` (Streamlit 1.64, управляемый виджет): `st.session_state["active_tab"]` инициализируется из `st.query_params["tab"]` один раз (только если ключа ещё нет в state — стандартный паттерн задания дефолта виджета), после выбора значение синхронизируется обратно в `query_params`. Повторный клик по уже выбранному пункту в `segmented_control` снимает выбор (вернёт `None`) — обработано через отдельный `_last_active_tab` в session_state, не через ключ виджета (Streamlit запрещает менять `session_state` виджета после его инстанцирования в этом прогоне). Проверено через `streamlit.testing.v1.AppTest` в контейнере: `query_params["tab"]="Источники"` → `session_state["active_tab"] == "Источники"` без исключений — то есть на первом же прогоне (эквивалент F5) открывается верная вкладка. Контейнер пересобран и перезапущен, `curl` (с URL-кодированной кириллицей) → HTTP 200.

## 2026-09-24 -- issue #272 (доработка): зависимость вынесена из requirements.txt

- Правка `requirements.txt` инвалидирует слои pip и chromium (тяжёлая перекачка). `streamlit-sortables` перенесён в `requirements-extra.txt`; в Dockerfile этот слой стоит после chromium/node и перед `COPY . .` (с кэшем pip). Правило: новые зависимости — в `requirements-extra.txt`; `requirements.txt` не трогать без необходимости.
- `requirements.txt` возвращён к состоянию до #273 (слои pip/chromium берутся из кэша).

## 2026-09-24 -- issue #272: выбор колонок, порядок и ширина с сохранением

- `ui/table_utils.py`: `column_settings(table_key, columns, base_config)` — popover «⚙ Колонки» (показывать, порядок drag-and-drop через `streamlit-sortables`, ширина small/medium/large, Сохранить/Сбросить); `merge_settings` (новые колонки в конец, удалённые пропускаются, «Выбор»/«Название» не скрываются), `load_prefs`/`save_prefs` (атомарно).
- Хранение: `config/ui_prefs.json` (в .gitignore, каталог config смонтирован в контейнер), ключ = таблица (`results`, `documents`), только технические имена колонок.
- Подключено в `results_tab` и `documents_tab`; колонка ссылки теперь «Ссылка» из COLUMN_LABELS. Остальные таблицы (dashboard, agents_status, site_publish — read-only st.dataframe) — следующим шагом.
- Ограничение Streamlit: ручное перетаскивание/растягивание в самой таблице в Python не возвращается, поэтому порядок и ширина задаются в popover.
- Проверка: `pytest` весь зелёный (+5 тестов test_table_prefs), AppTest обеих вкладок без исключений; drag-and-drop в браузере не проверялся.

## 2026-09-24 -- issue #270: таблица «Документы» по образцу «Результатов»

- Новый `ui/table_utils.py` (COLUMN_LABELS, `localize` — label_of для direction/category/doc_type, `link_column`, `datetime_column`); используется в `results_tab` и `documents_tab` (заголовок doc_type в «Результатах» теперь «Тип»).
- `ui/documents_tab.py`: русские заголовки, колонки Выбор/Название/Ссылка (source_url из sidecar)/Домен/Направление/Категория/Тип/Очищен/В GAR/Ошибка/Добавлен (mtime sidecar); убраны doc_id/raw/metadata/дубль error.
- Фильтры: поиск по названию и домену, статус «В GAR», домен со счётчиком, направление. Сортировка: ошибки, не загружены, загружены; затем по названию.
- Bulk: «Загрузить в GAR выбранные», «Удалить выбранные»; блок «по одному» и кнопка «Загрузить все» убраны (`_ingest_one/_delete_one` удалены, `_delete_files` общий).
- Проверка: `pytest` — 309 passed; AppTest рендера вкладки без исключений (248 документов).

## 2026-09-24 -- issue #256 (ADR-013): GAR — источник справочников, русские labels в UI
- `gar_schema.option_labels()` + `sync_from_gar` пишут в `categories.yaml` секцию `labels` ({field: {value: label}}).
- `schema.load_dictionaries()` для дефолтного пути накладывает directions+labels из `config/gar_schema_cache.json` (без сети); yaml — офлайн-фолбэк. `schema.label_of(dicts, field, value)` — label или value.
- `format_func`/labels: upload_tab (3 формы), search_tab, documents_tab (фильтр), results_tab (колонки direction/category/doc_type). В данных — slug.
- Вкладка «Справочники» — read-only + «Обновить из GAR» (`sync_from_gar`); CRUD убран (`save_dictionaries`/`validate_dictionaries` остались в schema.py).
- Проверка: `pytest tests` — 300 passed; `sync_from_gar --dry-run` отдаёт labels (zdorove → «Здоровье»); тесты `tests/test_option_labels.py`.

## 2026-09-24 -- issue #253: UI результатов — русские заголовки, формат даты, скрыты лишние столбцы

- `ui/results_tab.py`: все заголовки на русском (Выбор, Название, Домен, Направление, Категория, Тип документа, Дубль, Статус, Найдено).
- `found_at` выводится DatetimeColumn в формате DD.MM.YYYY HH:mm, сортировка по datetime работает корректно.
- Столбец `snippet` убран из таблицы (фильтр по snippet в text_input сохранён).
- `title` кликабельный (LinkColumn → url), столбцы `url` и `open` удалены.
- **Скрыты из UI** (остаются в БД, показ отложен до проработки UX):
  - `relevance_score` — релевантность источника запросу (ранжирование выдачи).
  - `license_status` — юридический статус использования контента (open/restricted/unknown, заполняется при approve).
  
  Это независимые оси: высокорелевантный источник может иметь ограниченную лицензию, и наоборот.
- Проверка: синтаксис OK. Коммит aaada6f, issue #253 closed.

## 2026-09-20 -- issue #224: publish_permission в реестре источников

- `config/licenses.yaml`: поле `publish_permission` по домену (not_set/not_required/granted/denied), отдельно от `status` (ADR-0013, ADR-0018 п.3).
- `src/license/checker.py`: `PublishPermission`, `PUBLISH_PERMISSION_LABELS`, `parse_publish_permission`; `LicenseCheckResult.publish_permission`; новые домены пишутся с not_set. Записи без поля читаются как not_set (миграция ленивая, yaml массово не переписывался; поле проставляется при сохранении в UI).
- UI «Источники»: selectbox «Разрешение на публикацию» (Не выбрано / Разрешение не требуется / Разрешение получено / Разрешение запрещено).
- Проверка: tests/test_license_checker.py (+4).

## 2026-09-19 -- issue #221: ссылка из «Источник» для ручных черновиков

- `publish.effective_source_url`: для `manual:` и http(s) в source_name в GAR уходит этот URL (и домен). Нужна повторная публикация уже опубликованных.
- Проверка: tests/test_news_manual.py, test_news_publish.

## 2026-09-19 -- issue #219: 422 при публикации ручного черновика + редактируемый «Источник»

- Причина: у `manual:<uuid>` пустой netloc -> `source_domain` пуст -> GAR 422.
  Fix: `publish.MANUAL_SOURCE_DOMAIN="manual"` как fallback в build_metadata.
- UI «Новости»: поле «Источник» (source_name) редактируется в карточке любой
  новости (EDITABLE_FIELDS += source_name).
- Проверка: tests/test_news_manual.py (+2), test_news_db/test_news_publish.

## 2026-09-19 -- issue #217: ручное создание черновика новости

- Вкладка «Новости»: expander «Создать черновик вручную» (ui/news_tab.py) ->
  `src/news/manual.py::create_manual_draft` (без LLM/лицензии, status=draft).
  source_name по умолчанию «Редакция» (редактируется), ссылка необязательна:
  пусто -> `manual:<uuid>` (source_url UNIQUE NOT NULL), дубль URL -> ValueError.
- Вкладка «Источники»: блок «Добавить новость по ссылке» перенесён в начало.
- Проверка: tests/test_news_manual.py (3) + test_news_db/test_news_publish — 30 passed.

## 2026-09-19 -- issue #208: добавление новости по ссылке — чистка текста, LLM в docker, num_ctx 8192

- Проблема: UI «Добавить новость по ссылке» (#183) для t-l.ru давал «LLM не
  смог собрать черновик». Причины: (1) в контейнере endpoint `127.0.0.1:11434`
  → Connection refused; (2) Ollama `context_length=4096` резал вход, модель
  галлюцинировала; (3) в LLM шёл весь fit_markdown с шапкой/подвалом.
- Решение: `src/news/text_clean.py::clean_article_text` (вызывается в
  `generate_draft`): режет подвал по маркерам/блоку ссылок, шапку, подписи к
  фото, ссылки -> текст, лимит 6000 симв.; провайдер `ollama` (`/api/chat`,
  `options.num_ctx`, `format=json`) в `llm_draft.py`; `config/news_llm.yaml`:
  provider=ollama, num_ctx=8192; env `NEWS_LLM_ENDPOINT`/`NEWS_LLM_MODEL`
  переопределяют yaml (gar-deploy: ds-search -> `host.docker.internal:11434/api/chat`);
  статус `llm_unavailable` (httpx.TransportError) + `not_relevant` в UI и CLI.
- Проверка: `tests/test_text_clean.py` (8), test_llm_draft/test_news_collect/
  test_collect_rss — 28 passed; реальная статья 9137 -> 4267 симв.; в контейнере
  `scripts.add_news_by_url https://t-l.ru/395993.html` -> draft (news_items id=13), факты верны.
- Заметка: `data/raw/<домен>/` создаётся контейнером от root — запуск CLI с хоста
  падает PermissionError; запускать через `docker exec deploy-ds-search-1 python -m scripts.add_news_by_url <url>`.
## 2026-09-18 -- issue #202: fallback на archive при 403 delete в GAR

- Проблема: `revoke_news_item` делал hard delete через GAR API; если у
  сервисного аккаунта нет прав delete на датасете — 403 Permission
  denied, документ оставался опубликованным.
- Решение: `src/news/publish.py::revoke_news_item` — при
  `GarPublishError` с "403" в тексте делает fallback на
  `client.archive_document()` (issue #133, скрывает из /public и
  retrieval), `gar_document_id` чистится как обычно; результат содержит
  `archived_fallback: True`. Любая другая ошибка по-прежнему
  пробрасывается наверх.
- Тесты: `tests/test_news_publish.py` (16 passed).
- PR #203 (ds_search), смержен в main. Issue #202 закрыт.

## 2026-09-18 -- issue #194 (ADR-0012): агрегаторы — атрибуция на первоисточник из текста статьи

- Проблема: wildcar.ru — агрегатор, перепечатывает новости; атрибуция
  указывала на wildcar, а не на реального автора (пример: статья про
  DJ JP на Rock in Rio, первоисточник sonoticiaboa.com.br указан в
  тексте строкой "Источник: [домен](url)").
- Решение: `config/licenses.yaml` -- новое поле `is_aggregator: bool`
  (wildcar.ru = true); `src/license/checker.py::LicenseCheckResult`
  прокидывает его дальше; `src/discovery/download.py` пишет
  `is_aggregator` в meta; новый `src/news/aggregator.py::
  extract_primary_source_url()` парсит ссылку из уже скачанного
  markdown-текста статьи (паттерн "Источник:/Source:/Fonte: [x](url)");
  `src/news/collect.py::_collect_one` при `is_aggregator=True`
  подменяет `source_url`/`source_name` в LLM-source на найденный
  первоисточник перед `generate_draft`. Первоисточник НЕ краулится —
  его домен не обязан быть в `licenses.yaml`, summary делается по
  тексту агрегатора.
- UI: `ui/sources_tab.py` -- чекбокс "Агрегатор" в форме домена, бейдж
  "🔁 агрегатор" в заголовке.
- Проверено сквозным прогоном: `add_news_by_url.py` на статье wildcar
  про DJ JP -> news_items.source_url = sonoticiaboa.com.br (не wildcar).
- Тесты: новый tests/test_aggregator.py (3 теста); полный прогон
  license/collect/download/aggregator -- 28/28 passed.
- ADR-0012 (`docs/adr/0012-aggregator-source-detection.md`), PR TBD
  (Closes #194), в project #4.

## 2026-09-18 -- issue #186: classify() тихий фейл + невалидные дефолты age/category ломали publish (422)

- Root cause: `classify()` глотал исключение LLM без логирования;
  `metadata/profile.py::DEFAULT_CATEGORY = "basic"` не входит в опции
  controlled-поля `category` текущей GAR-схемы (для `direction=news`
  своей категории нет вовсе) -> 422 unknown value; `build_metadata()` не
  добавлял ключ `age` вовсе, если classify() не определил его -> 422
  age must not be blank. Воспроизведено на wildcar.ru (нет записи в
  gar_mapping.yaml).
- Фикс: `classify()` -- `logger.exception(...)` в except с domain/title;
  `profile.py` -- убран невалидный DEFAULT_CATEGORY, category не
  проставляется без явного значения; `news/publish.py` -- добавлен
  `FALLBACK_AGE = "Все возрасты"` (сверено с gar_schema_cache.json),
  build_metadata() всегда проставляет age.
- Тесты: tests/test_metadata_profile.py, tests/test_news_publish.py
  обновлены под новое поведение; полный прогон 243/243 passed.
- PR #190 (branch fix/186-clean, Closes #186), в project #4.

## 2026-09-17 -- LLM-эндпоинты пофикшены, first news item сгенерирован, публикация блокируется (#180, #181 заведены)

- Root cause: `classify_llm.yaml` указывал на `router.cheap` (не резолвится,
  пустой api_key); `news_llm.yaml` -- на `host.docker.internal:11434`
  (не резолвится из голого WSL). Реальный Ollama слушает на
  `127.0.0.1:11434`. Оба конфига поправлены на 127.0.0.1, модель
  `qwen2.5-coder:14b`.
- Тестовый прогон разового сборщика (`/tmp/one_news2.py`, вне пайплайна):
  fetch/scrape/LLM-драфт прошли, item id=7 "Тренировки особых детей:
  успех и надежда" сгенерирован, статус в локальной БД `published`.
- Публикация в GAR падает 422 `age must not be blank`: news/publish.py::
  build_metadata() использует старый build_ingestion_metadata (issue #49/
  ADR-003), не знает про age/target_audience/direction/doc_type. Готовый
  classify.classify() (issue #91/эпик #88) не довязан к news-пайплайну.
- Заведены и залинкованы в project #4:
  - #180 -- RSS-фиды в rss_sources.yaml нерабочие (downsideup/miloserdie/
    asi/nakedheart/takiedela) + нет relevance-фильтра после SearchChain
    (пример нерелевантных драфтов id=2-5, pravmir). Обход: AMP-теги.
  - #181 -- [Epic] связать news/publish.py::build_metadata() с
    metadata/classify.classify() перед ingestion (багфикс, ADR не нужен).
- TODO: удалить `/tmp/one_news2.py` и черновики id=2-5 после решения по
  ним; реализовать #181, затем повторно опубликовать item id=7.

## 2026-09-17 -- feat: FirecrawlProvider первым звеном SearchProviderChain (#178, PR #179, merged)

- Проверка (issue #169, #168, #165 закрыты ранее): тесты чинятся
  запуском через `.venv/bin/python -m pytest`, а не `.venv/bin/pytest`
  (иначе `ModuleNotFoundError: src`); 20/20 зелёные, 5 RSS-доменов в
  licenses.yaml подтверждены.
- Brave free tier снят с продажи (нужна карта, проверено на реальном
  дашборде), Tavily заблокирован на уровне сети (TLS проходит, HTTP-ответ
  не приходит — проверено и с keyless, и с реальным TAVILY_API_KEY).
- Проверена доступность из рабочей сети: api.firecrawl.dev отвечает
  штатно (200), free tier 1000 кред/мес без карты.
- `src/search/firecrawl.py` (FirecrawlProvider), chain теперь
  Firecrawl -> Brave -> Tavily (`scripts/collect_news.py`,
  `ui/search_tab.py`), 10 новых тестов, полный набор 241/241.
- ADR-011 дополнен разделом "Дополнение от 2026-09-17".
- Открыто: реальный прогон `collect_news.py` с боевым FIRECRAWL_API_KEY
  ещё не делался (ключ проверен отдельным запросом к API, не через пайп).

## 2026-09-17 -- ADR-011: Brave Search + RSS license-гейт (issue #164, эпик #167)

- issue #164: forbes.kz проверен -> deny (PR #166, п.2.2 соглашения
  запрещает использование вне личных целей без письм. согласия).
  tass.ru/iz.ru не проверены (ToS-страницы не гуглятся); полный список
  ~16 доменов из пилота #162 нигде не сохранён, Tavily keyless сейчас 403
  -> пилот не перезапустить без TAVILY_API_KEY.
- ADR-011 (docs/adr/ADR-011-brave-search-rss-licenses.md): т.к. Tavily
  нестабилен второй день, а объём нужен скромный (10-50/день) --
  добавить Brave Search (free tier) первым звеном в SearchProviderChain,
  Tavily фолбэком. Приоритет: 5 из 8 доменов в config/rss_sources.yaml
  (ADR-010) без записи в licenses.yaml -> RSS-канал их не скачивает вообще
  -- это выше по приоритету, чем #164 (курируемый список vs поиск).
- Заведены issues (эпик #167, все в project #4):
  #168 ToS 5 RSS-доменов (asi.org.ru, philanthropy.ru, takiedela.ru,
  nakedheart.online, rusfond.ru), #169 BraveProvider в SearchProviderChain.
- Не сделано: сама реализация BraveProvider и ToS-разбор -- только ADR
  и задачи, код не трогал.

## 2026-09-17 -- fix: collect_news.py keyless Tavily + Docker infra (#162, merged)

- PR #163 (merged). Closes #162.
- Keyless Tavily режим (`X-Tavily-Access-Mode: keyless`), `playwright install`
  в Dockerfile, `host.docker.internal` для Ollama из контейнера,
  2 записи в `licenses.yaml` (news.un.org, unicef.org).
- Итог тестового прогона: `drafted=2`.
- Открыто: расширить `licenses.yaml` ещё на ~16 доменов (tass.ru, iz.ru,
  forbes.kz и др.) -- нужна юр. проверка ToS каждого;
  на main падают `test_classify` + 2x `test_collect_rss` (не связано с
  этим PR, доп. issue заведён -- #165).

## 2026-09-15 -- release 0.1.21 closed; next 0.1.22

- All Project #1 items targeted to 0.1.21 are Done/closed. Release notes published; next release target is 0.1.22.

## 2026-09-14 -- ADR-0009: staged real-source re-crawl adapter реализован

- Root ADR: `ds/docs/adr/0009-real-source-recrawl-reload.md`.
- Requirements: `ds/docs/requirements/real-source-recrawl-reload.md`.
- Решение: crawler выдаёт staged `.md`+`.json` и typed JSON; до validation
  рабочие raw/state не меняются. Canonical URL identity, `doc_id` стабилен;
  provenance merge сохраняет отсутствующие manual metadata и не удаляет по
  `null`. Реализация GAR update остаётся в ds_ingestion: PATCH metadata,
  затем PUT content, rollback snapshot при ошибке PUT, lock per document.
- `recrawl_cli` принимает отдельный staging-каталог, читает исходный sidecar
  только из рабочего raw, возвращает typed JSON с provenance/correlation ID и
  завершает CLI с exit 1 при rejection; рабочие raw/state при staged запуске не
  перезаписываются.
- Проверки: focused crawler tests 6 passed; `py_compile`; `git diff --check`.
- Следующий bounded slice: **ds_ingestion orchestration owner**.


Полная история 2026-09-10 -- 2026-09-17 перенесена в
`docs/archive/current-status/CURRENT_STATUS-2026-09-10_2026-09-17.md`.

## 2026-09-18 -- issue #184: licenses.yaml автосоздание pending_manual_review

- ADR-0013 (`ds/docs/adr/0013-license-registry-auto-pending.md`).
- `src/license/checker.py::check_license` теперь пишет заготовку
  `pending_manual_review` в `config/licenses.yaml` при первой встрече
  неизвестного домена (idempotent, `_register_pending`).
- `ui/sources_tab.py`: явный warning + `expanded=True` + селектбокс без
  предвыбранного статуса для непроверенных доменов; кнопка "Сохранить"
  заблокирована пока статус не выбран (раньше молча дефолтился на `allow`).
- Тесты: `tests/test_license_checker.py` (2 passed).
- PR #193 (branch `fix/184-license-registry-auto-pending`), Closes #184.


## 2026-09-19 -- issue #204: добавление документа по URL через админку (ADR-0014)

- ADR-0014 (`ds/docs/adr/0014-single-url-manual-ingest.md`), parent ds_ingestion#30.
- `src/crawler/manual_add.py::add_manual_document` — переиспользует
  `SourceCrawler.recrawl_url()` (ADR-0009). Домен резолвится в существующий
  source (пишет в его data/raw/<name>/) либо в псевдо-source `manual`
  (data/raw/manual/). Дубликат по canonical_url (doc_id уже существует)
  блокируется до вызова crawl; license gate (ADR-0013) — неизвестный домен
  авто-pending_manual_review, сохранение блокируется до ручного статуса.
- `ui/documents_tab.py`: поле URL + кнопка "Добавить документ" сверху вкладки
  "Документы"; статусы added/duplicate/license_pending/license_denied/failed.
- ds_ingestion/ds_site без изменений (подхватывается обычным CLI
  `python -m src.adapter.cli manual`).
- Тесты: `tests/test_manual_add.py` (3 passed: success, unknown domain
  blocked, duplicate blocked). Полный набор: 260 passed.
- PR: branch `feat/204-manual-url-add`, Closes #204.

## 2026-09-19 -- issue #206: нормализация домена в license-гейте
- Причина: `check_license` искал домен по точному `netloc` (с `www.`/портом);
  запись `pravmir.ru` не находилась для `www.pravmir.ru`, создавался дубль
  `pending_manual_review` (#184) и «Добавить новость по ссылке» (#183) блокировался.
- `src/license/checker.py`: `normalize_domain()` (lower, без порта и `www.`),
  применяется в `check_license`/`_register_pending`; запасной поиск по старому
  ключу `www.<домен>`. UI «Источники»: счётчики по нормализованному домену.
- `config/licenses.yaml`: ключи без `www.`, удалён дубль `www.pravmir.ru` и
  `deny`-домены (diariodorio.com, takiedela.ru, www.unicef.org) — они снова
  появятся как pending при первой встрече, скачивание не идёт.
- Тесты: `tests/test_license_checker.py` (+4). Полный набор: 264 passed.
- PR: branch `fix/206-license-domain-normalize`, Closes #206.

## 2026-09-19 — ревью загрузки новости по URL (#211)
- num_ctx: единый дефолт 8192 в LlmConfig; collect.py: httpx.HTTPError → llm_unavailable.
- Решено: ds-search запускается от uid 1000 (gar-deploy#25), data/raw создаётся от vector, CLI с хоста работает.

- 2026-09-19: fix #214 — Dockerfile: PLAYWRIGHT_BROWSERS_PATH=/ms-playwright, chromium запечён в образ (контейнер под 1000:1000, HOME=/tmp). Нужен docker compose build ds-search.

### ds_search#225 — вкладка «Внешний сайт» (2026-09-20)
- ui/site_publish_tab.py + src/site_publish/runner.py: кнопка «Пересобрать внешний сайт» запускает node scripts/publish-pages.mjs из ds_site (DS_SITE_DIR, по умолчанию ../ds_site; node — из PATH или ~/.nvm, предпочтительно v22) отдельным процессом; лог/статус в data/site_publish/. Подтверждение обязательно, есть пробный прогон (--dry-run). Показ статуса, лога и счётчиков (опубликовано / отфильтровано not_set и denied — разбор вывода export-content). Из docker-контейнера недоступно (нужен ds_site, node, gh) — запускать ds_search локально в WSL.
- Проверка: tests/test_site_publish.py, AppTest вкладки, реальный dry-run: exit 0, 0 опубликовано (articles 98, news 11, glossary 62, links 126 — not_set). Решено: место — Streamlit ds_search (ADR-0018 п.7).

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

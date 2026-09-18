## 2026-09-18 -- fix: publish 403 + volume-mount ds-search (gar-deploy#21, #185, #186)

- gar-deploy#21 закрыт: `deploy/docker-compose.yml` для ds-search теперь
  монтирует `../ds/ds_search/data:/app/data` и `../ds/ds_search/config:/app/config`
  (раньше запекались в образ, терялись при пересборке). Данные не потеряны:
  перед переключением смёржена хостовая копия news.db (id 1-6) с актуальной
  копией из работавшего контейнера (id 7-11) -- итог 11 записей.
- Публикация новости в GAR падала `403 Permission denied` -- причина в двух
  местах, оба исправлены руками (нужно закрепить в коде/миграциях, см. issues):
  - `acl_rules` (gar-core-api): у `ds-search-news-publish` было только `read`,
    добавлена запись `write` на датасет `81f35f18-8d32-458e-bf33-ddb68349e015`.
    Issue ds_search#185 -- перенести фикс в seed/миграцию, разобраться с
    остальными сервисами.
  - `ds-ingestion.env` (общий для ds-ingestion/ds-search) задавал
    `GAR_USER_ID=ds-ingestion-adapter`, перебивая дефолт кода
    `ds-search-news-publish`; в compose добавлен явный
    `environment: GAR_USER_ID=ds-search-news-publish` для сервиса ds-search.
- После фикса 403 всплыл `422`: LLM-классификатор (`metadata/classify.py`)
  тихо падает (`source: "none"`) для новых доменов вне `gar_mapping.yaml`
  (пример: wildcar.ru) -- `age` остаётся пустым, обязательное поле GAR.
  Дефолт `category: "basic"` дополнительно оказался невалидным
  controlled-значением. Issue ds_search#186 -- логирование причины падения
  classify(), дефолт для age, валидный/отсутствующий category при needs_review.
- Новость "Учёные отключили лишнюю хромосому 21..." опубликована вручную
  (`age="все возрасты"`, без `category`) -- `document_id: 93269faa-...`,
  status `indexed`, отображается на ds_site `/news`. Пользователь подтвердил.

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

## 2026-09-14 -- материалы GAR: ACL для admin UI

- Исправлен HTTP 403 при загрузке списка материалов: в GAR выдан idempotent
  ACL `read` для `ds-search-news-publish` на dataset
  `81f35f18-8d32-458e-bf33-ddb68349e015`.
- Проверка: `GET /ingestion/documents?dataset_id=...&status=indexed` с
  `X-User-ID: ds-search-news-publish` вернул документы.

## 2026-09-14 -- issue #141, #142: Full source reload (root ADR-0007, ds_ingestion#7)

- Root ADR: `ds/docs/adr/0007-full-source-reload-pipeline.md`.
- #141: re-crawl конкретного документа по URL/doc_id — сделано. `SourceCrawler.
  recrawl_url(url)` (src/crawler/crawler.py) краулит один URL (без deep-crawl
  стратегии), применяет ту же фильтрацию (thin/catalog/pdf-teaser), пишет
  .md/.json по тому же doc_id (sha256 от canon_url — детерминирован, файлы
  перезаписываются). CLI: `python -m src.crawler.crawler --recrawl --source
  <name> --doc-id <id>` (URL берётся из sidecar) или `--url <url>` явно.
  Вызывается reload-пайплайном ds_ingestion (issue #8) как subprocess.
  PR ds_search#... (branch feat/141-recrawl-url).
- #142: заменить эвристику детекта битых файлов ("1 строка") на устойчивую
  (буквальные \n вместо переноса строки) — сделано. `scripts/detect_broken_files.py`
  сканирует data/raw/<source>/*.md на литеральный `\n`, пишет
  broken_files_report.md. PR ds_search#144 (branch feat/142-detect-broken-files).
- #145: кнопка "🔄 Перезагрузить из источника" в `ui/materials_tab.py`
  (заменяет ds_site#23, закрытый — ADR-0005: админка только тут). POST
  {DS_INGESTION_URL}/reload_by_gar_id {gar_document_id} (ds_ingestion#13),
  показывает changed_fields/preserved_fields/content_replaced. Auth не
  реализован — прода нет. PR ds_search#146 (squash, смёржен).

## 2026-09-14 -- issue #139: doc_type не проставлялся статьям веб-краулинга

- Причина: `doc_type` не в REQUIRED_FIELDS, не передавался в
  `build_ingestion_metadata()` из `crawler.py::_save/_save_pdf` и
  `download.py::download_single/_save_pdf` (в отличие от всех остальных
  вызывающих сторон). 107/300 документов в gar_core.documents имели
  `metadata.doc_type = NULL` -> `/articles` на сайте показывал 1 статью.
- Фикс: `doc_type="article"` добавлен во все 4 места. PR
  ds_search#140 (смёржен, Closes #139).
- Бэкфилл 103 существующих документов через `PATCH /ingestion/documents/{id}`
  (без прямых UPDATE в Postgres) — `ds_ingestion/scripts/backfill_doc_type_article.py`,
  ds_ingestion PR#6 (смёржен). Проверено: `GET /public/documents?doc_type=article`
  отдаёт 104 (было 1).
- Остались 4 документа без doc_type — не относятся к family_support/downsideup
  (легаси "Евангелие"/"Деяния", 2 экспорта glossary/resource_directory из
  ds_search) — вне scope этого issue.

## 2026-09-14 -- issue #138: просмотр статьи по лицензии (ADR-0006)

- ADR-0006 принят: полный текст на сайте, если canonical_md скачан
  (переиспользован существующий признак `assets.canonical_md.available`,
  отдельное поле `full_text_available` заводить не стали).
- gar-core-api: `GET /public/documents/{id}` и `/public/documents/{id}/content`
  (`services/document_search_service.get_document_detail`). Тесты зелёные
  (7 passed по document_search/public). PR gar-core-api#315 (смёржен).
- ds_site: роут `/articles/[id]` — полный текст + автор + ссылка на источник,
  либо карточка метаданных + ссылка без текста. Прокси
  `app/api/gar/documents/[id]` и `.../content`. Заголовки в `/articles` теперь
  ссылки на `/articles/[id]`. PR ds_site#21 (смёржен, Closes #138).
- Issue #138 закрыт.


Архив 2026-09-10 .. 2026-09-13 перенесён в `docs/archive/current-status/CURRENT_STATUS-2026-09-10_2026-09-13.md`.

## 2026-09-17 — issue #168: ToS-check 5 RSS-доменов (эпик #167, ADR-011)

- `config/licenses.yaml`: добавлены записи для 5 доменов из
  `config/rss_sources.yaml`, ранее молча блокировавшихся license-гейтом
  (issue #3, ADR-010) — asi.org.ru, philanthropy.ru, takiedela.ru,
  nakedheart.online, rusfond.ru.
- **takiedela.ru → `deny`** (единственный из пяти): футер сайта требует
  явного согласования с правообладателями для размещения материалов на
  сторонних ресурсах, а не только атрибуции.
- Остальные 4 домена → `attribution_required`, явного запрета на
  перепечатку/цитирование не найдено (asi.org.ru — с оговоркой ≤30%
  текста без запроса в редакцию, фото отдельно; philanthropy.ru — проект
  «Филантроп» закрыт).
- Проверка: `yaml.safe_load(config/licenses.yaml)` — 15 записей, парсится
  без ошибок.
- PR #170 (squash, merged), issue #168 закрыт (Closes).

## 2026-09-17 — issue #171: BraveProvider первым в chain (эпик #167, ADR-011)

- src/search/brave.py: BraveProvider — free tier 2000 запросов/мес,
  X-Subscription-Token заголовок, 401/429 -> QuotaExceeded.
- chain.py docstring обновлён: порядок Brave (первый) -> Tavily (фолбэк).
- ui/search_tab.py: _build_chain() -> SearchProviderChain([BraveProvider(), TavilyProvider()]).
- 	ests/test_brave_provider.py: 7 тестов (parse/headers/quota/errors).
- Полный прогон: 228 passed, 3 fail не связаны (test_classify эпик,
  test_collect_rss — существовали до issue).
- PR #173, Closes #171.

## 2026-09-17 — issue #165: падали test_classify + test_collect_rss на main

- Причина разная для каждого теста (не общий баг):
  - test_collect_rss x2: PR #161 добавил tests/test_collect_rss.py и
    scripts/collect_rss.py, но саму функцию `collect_rss` в
    src/news/collect.py не добавил (AttributeError). Реализована по
    образцу collect_news(): rss.fetch_all -> dedup по
    news_items.source_url -> _collect_one (тот же license-гейт/
    download/LLM-draft). _collect_one расширен опциональными
    source_name/source_published_at, поведение collect_news не меняется.
  - test_classify x1: НЕ связано с RSS. classifier_keywords.yaml
    (раздел category) и сам тест используют старую таксономию категорий
    (speech_development, direction=methodology), а config/categories.yaml
    мигрировал на новую slug-таксономию ещё в PR #77 —
    suggested_category/suggested_direction молча всегда None для
    реальных документов с тех пор. Требует content-решения по маппингу
    (какие ключевики к какому из текущих разделов) — вынесено в
    issue #174, не чинилось в рамках #165.
- Прогон: tests/test_collect_rss.py — 2/2 passed; полный набор —
  230 passed, 1 failed (issue #174, ожидаемо).
- PR #175 (squash, merged), issue #165 закрыт.


## 2026-09-17: Автосбор одной новости про СД (ручной прогон)

**Задача:** найти и скачать одну новость про синдром Дауна, опубликовать в GAR → отображается на `ds_site` `/news`.

**Найдено (баг, требует issue в ds_search):** штатный `python -m scripts.collect_news` (SearchChain: Firecrawl/Brave/Tavily по запросам из `config/news_search_queries.yaml`) реально работает, но без промежуточного вывода (print только в конце прогона) — тишина в консоли ≠ зависание. За ~6 мин создал 4 черновика (`news_items` id=2..5), но все — нерелевантные статьи с pravmir.ru (не про СД). Причина: после SearchChain нет тематической фильтрации результатов, только license-гейт + дедуп по URL — поисковый провайдер отдаёт мусорные хиты, пайплайн их проглатывает. **TODO: завести issue в ds_search** — добавить relevance-фильтр (по ключевым словам заголовка/сниппета или LLM-классификатор) после `chain.search()` в `src/news/collect.py::collect_news`, до скачивания.

**Также:** RSS-ветка (`src/news/rss.py::fetch_all`) тоже не фильтрует по теме — берёт все записи фида без разбора. Для гарантированной релевантности первого прогона ограничился источником `downsideup.org` (профильный фонд, все статьи по теме).

**Статус:** черновики id=2..5 остались в БД со статусом draft (не про СД, публиковать не надо, можно удалить/оставить на потом при доработке фильтра). Разовый скрипт `_one_news.py` в ds_search/ (не коммитить, временный) переиспользует `src.news.collect._collect_one` + `src.news.db` + `src.news.publish` для сбора/публикации ровно одного новостного айтема — ограничен на downsideup.org, в процессе выполнения.

**Next steps:** 1) доисполнить `_one_news.py` (downsideup.org) → published → проверить `ds_site:3001/news`. 2) Завести issue в ds_search "collect_news: нет relevance-фильтра результатов поиска, публикует нерелевантные статьи (пример: pravmir.ru id=2..5)" + линк в projects/4. 3) Решить судьбу черновиков id=2..5 (удалить или разметить rejected).

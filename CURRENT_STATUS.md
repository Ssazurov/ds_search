# Progress ds_search

## Issue #2 — краулер источника (Crawl4AI, ADR-001)
Статус: ЗАВЕРШЕНО, прогнан на downsideup.org.

- Реализация: `src/crawler/crawler.py`, `config.py`, `filters.py`
  (BestFirstCrawlingStrategy + KeywordRelevanceScorer, FilterChain).
- Выход: `data/raw/<source>/<hash>.md` + `<hash>.json` (source_url,
  source_domain, title, direction, license="pending_check", content_path).
- Прогон на downsideup.org: собрано 100 документов (лимит max_pages=100),
  200 файлов в data/raw/downsideup.
- Известная проблема: 1 PDF-ссылка (`.../Напутствие другим родителям_2023.pdf`)
  роняет запрос — Playwright трактует переход как скачивание файла
  (`Page.goto: Download is starting`), а не обычную навигацию. На общий сбор
  не повлияло (страница просто пропущена), но нужно поправить: исключать
  прямые файловые ссылки (.pdf/.doc/...) из deep-crawl и скачивать их
  отдельным http-запросом, а не через browser.goto.
- license="pending_check" — реальное значение проставит issue #3
  (src/license/checker.py), см. ADR-001 п.3.
- Не закоммичено в git — ждёт запроса пользователя.

## Issue #3 — проверка лицензии/ToS источника (ADR-001 п.3)
Статус: РЕАЛИЗОВАНО, не прогнано на реальном сборе, не закоммичено.

- `src/license/checker.py`: `check_license(domain, base_url)` —
  1) robots.txt (httpx + urllib.robotparser): explicit disallow -> `deny`;
  2) реестр `config/licenses.yaml` (ручная оценка ToS по домену) -> `allow`/
     `attribution_required`/`deny`; домен вне реестра -> `pending_manual_review`
     (трактуется как "не скачивать", безопасный дефолт).
  `LicenseCheckResult.downloadable` / `.build_attribution(title, source_url)`.
- `config/licenses.yaml`: заведена запись `downsideup.org: attribution_required`
  (подвал сайта требует активную ссылку на downsideup.org, проверено вручную
  2026-08-24).
- `src/crawler/crawler.py` интегрирован: `check_license` вызывается один раз
  на источник в `run()` перед обходом; если `not downloadable` — обход не
  запускается, лог-предупреждение, `saved=[]`. В метаданных документа поле
  `license` теперь = реальный статус (не `"pending_check"`), добавлено поле
  `attribution` (сформированная строка атрибуции или `null`).
- requirements.txt: добавлен `pyyaml`.
- Не сделано: бэкфилл уже собранных 200 файлов downsideup (`license:
  "pending_check"` в data/raw) — реестр теперь их бы пометил
  `attribution_required`, но существующие json не обновлены (не входило в
  формулировку issue #3, отдельная задача при необходимости).

## ADR-001 обновлён (2026-08-24)
Добавлен п.3a: очистка/фильтрация контента — обязательный этап между
краулингом и загрузкой в GAR (nav/footer/спецверсии сайта в raw markdown,
страницы-пустышки типа "видео без текста"). Реализация — отдельный issue,
пока не заведён.


## 2026-08-25 — issue #4 (доменный профиль метаданных): механизм решён

- Механизм записи: per-dataset динамический словарь метаданных gar-core-api
  (`DatasetMetadataField`/`DatasetMetadataOption`, роутер
  `routers/metadata_dictionary.py`, `POST /datasets/{id}/metadata-fields`) —
  уже готовая инфраструктура, не требует ни расширения metadata_schema.yaml
  (та схема заточена под product/doc_type техдокументации gar-metadata-worker),
  ни новой Postgres-таблицы (дублировала бы существующий механизм).
- `config/categories.yaml` — стартовый словарь категорий по 4 направлениям
  (methodology/medicine/law/science), из раздела 3.0 видения.
- `src/metadata/schema.py` — константы (DIRECTIONS, DOC_TYPES,
  TARGET_AUDIENCES, LICENSE_STATUSES, REQUIRED_FIELDS) + загрузчик
  categories.yaml, для использования адаптером в issue #5.
- ADR-001 п.2 обновлён (механизм зафиксирован), "Открытые вопросы" закрыты.
- Не сделано: сами поля через API gar-core-api ещё не заведены (нужен id
  датасета GAR под этот проект) — это часть issue #5, не #4.
- Комментарий с итогом оставлен в issue #4 (не закрыт вручную — решение
  оставлено пользователю).


## 2026-08-25 — ручной анализ качества корпуса downsideup.org (100 файлов)

Разобраны первые 5 + статистика по всем 100 json в data/raw/downsideup:
- 5/5 вручную проверенных документов — брак (главная страница, тизер к
  PDF-отчёту, 2x страницы "Электронная библиотека" без контента, страница
  пагинации). Ни один не содержит реального текста статьи.
- По всему корпусу: 10/100 — шаблонный title "Электронная библиотека -..."
  (JS-виджет не рендерится), 6/100 "Аналитика для прогресса" +6/100 "Новости"
  (листинги/пагинация ?PAGEN_1=), плюс дневник развития/календарь/форум/
  регистрация/дубли главной — суммарно ~38-45% корпуса не является статьями.
- Причина: EXCLUDE_PATTERNS в src/crawler/filters.py — англоязычные слаги,
  не матчат реальные (транслит) URL источника.
- Действия: ADR-001 дополнен п.3b; заведён issue #8 (актуализация фильтров
  краулера, sub-issue эпика #1); issue #6 дополнен конкретными критериями
  браковки (шаблонный title, PDF-тизер); комментарии-находки оставлены в
  issue #2 и #6.
- Не сделано: сам фикс фильтров (issue #8) и запуск content-cleaning
  (issue #6) — оба пока не реализованы, есть только уточнённая постановка.


## 2026-08-25 — research: boilerplate removal, применено к ADR/issue #6/#8

Пользователь принёс research-отчёт (Trafilatura/Boilerpipe/LTR-метрика/
Crawl4AI pruning filter). Полезное: Crawl4AI уже имеет встроенный
density-based content filter (PruningContentFilter -> fit_markdown) —
отменяет план писать свой regex-парсер под strip nav/footer в issue #6.
LTR (link-to-text ratio) взят как конкретная метрика для thin-content
порога в issue #6 и hard-cutoff в issue #8. Неприменимое (нейро-
приоритизация очереди, sitemap weights, Schema-парсинг) — отложено,
не блокирует MVP.
- ADR-001 п.3a дополнен.
- Комментарии-уточнения оставлены в issue #6 и issue #8.
- Не сделано: сама реализация (подключение PruningContentFilter в
  crawler.py, подбор LTR-порога на реальных данных) — по-прежнему в
  issue #6/#8, не реализовано.


## 2026-08-25 — issue #8 реализован (краулер: отбор страниц)

Код: src/crawler/config.py, filters.py, crawler.py.
- SourceConfig.exclude_slugs (RU-слаги downsideup: novosti,
  kalendar-sobytiy, forum, registratsiya, otzyvy,
  politika-konfidentialnosti, search, dnevnik-razvitiya) вместо общего
  англоязычного EXCLUDE_PATTERNS.
- Фильтр пагинации (*PAGEN_1=*, *PAGE=*, *page=*) в BASE_EXCLUDE_PATTERNS.
- canonicalize_url() — убирает fragment/utm_*/session-параметры, приводит
  trailing slash; используется до хэширования doc_id и для dedup между
  seed_urls (self._seen_urls в SourceCrawler).
- Hard-cutoff по длине PruningContentFilter.fit_markdown
  (SourceConfig.min_fit_markdown_chars, 200) перед сохранением — короткие
  результаты не пишутся в data/raw.
- PDF-тизеры: find_pdf_teaser_link() ищет прямую ссылку на PDF в html
  тонкой страницы, URL кладётся в SourceCrawler.pdf_queue (само скачивание
  PDF по очереди — не в scope #8, следующий шаг).
- Не сделано / вне scope: реальный запуск на downsideup.org для проверки
  на живых данных (нужен сетевой доступ), скачивание PDF из pdf_queue.


## 2026-08-25 — перезапуск краулера на живых данных, 10/10 статей

Старая папка data/raw/downsideup (100+ страниц, ~40-45% брак) удалена —
не закоммичена, заменена новым прогоном.
- seed_urls сужен до 1 URL: https://downsideup.org/o-sindrome-dauna/cifry-i-fakty/
  (по запросу пользователя).
- exclude_slugs дополнен: interaktiv, elektronnaya-biblioteka,
  fond-sindrom-lyubvi (после 1-го прогона — уводили в другие разделы/orgs).
- filters.py BASE_EXCLUDE_PATTERNS дополнен: "https://*.downsideup.org/*"
  (поддомены типа dnevnik-razvitiya-rebenka — DomainFilter по basedomain
  их не отсекает), "https://downsideup.org/" (голая главная), а также
  bare-root листинг "https://downsideup.org/analytics" /"/analytics/"
  (страница "Все материалы" со списком ссылок — не статья, hard-cutoff по
  длине fit_markdown её не ловит, т.к. есть вводный абзац).
- Итог 3-го прогона: 10/10 сохранённых документов — реальные статьи
  (1.9к-19к символов), проверено вручную по title+source_url+длине.
  Известная проблема с PDF-тизером (Page.goto: Download is starting) на
  https://downsideup.org/Lyudi-s-sindromom-Dauna-v-mire-statistika
  осталась (см. issue #2) — страница пропущена, на итог не повлияло.
- Изменено: src/crawler/config.py (seed_urls, exclude_slugs),
  src/crawler/filters.py (BASE_EXCLUDE_PATTERNS).


## 2026-08-25 — issue #11: PDF-тизеры теперь реально скачиваются

Проблема: страница-тизер `.../lyudi-s-sindromom-dauna-v-mire-statistika-i-nadezhnost-dannykh/`
сохранялась как "документ" без реального контента — `find_pdf_teaser_link()`
вызывался только при `fit_markdown` короче `min_fit_markdown_chars`, а у этой
карточки fit_markdown = 2080 символов (за счёт блока "Похожие материалы") —
порог пройден, PDF-ссылка не искалась. Также `pdf_queue` из issue #8 только
собирал URL, само скачивание не было реализовано.

- `src/crawler/filters.py`: добавлен `is_pdf_teaser_page()` — детект тизера
  по маркеру "скачать/открыть отчёт" рядом с `.pdf`-ссылкой в html, не
  зависит от длины fit_markdown.
- `src/crawler/crawler.py`: проверка `is_pdf_teaser_page()` выполняется
  первой (до фильтра по длине); при находке — `_download_pdf()` (httpx,
  прямой GET, не browser.goto — issue #2) сохраняет `.pdf` + `.json` в
  data/raw как обычный документ; `pdf_queue` остаётся fallback-ом на случай
  сетевой ошибки скачивания.
- ADR-001 п.3b уточнён.
- Прогон на живых данных (10 seed-статей, config без изменений): 10/10
  сохранено, 2 из них — реальные PDF (18 и 19 страниц, оба валидны),
  `pdf_queue=0`. Старая испорченная папка data/raw/downsideup
  пересобрана.

## Issue #6 (доп. подтверждение LTR-порога), PR #13
Ручная проверка 8 файлов data/raw/downsideup (без PDF): статьи LTR 0.05-0.12,
каталоги/листинги LTR 0.48-0.86 — порог 0.2-0.3 из ADR-001 п.3a подтверждён.
В `src/crawler/filters.py` реализованы `link_to_text_ratio()` и
`is_listing_page()` с hard-cutoff `LTR_CUTOFF = 0.3`; `src/crawler/crawler.py`
отбрасывает такие страницы до сохранения и пишет счётчик `skipped_listing`.
1 статья не по теме (фандрайзинг, LTR=0.12) — LTR это не ловит, нужен
отдельный keyword/URL-фильтр (следующий шаг, зафиксировано в ADR).
ADR-001 п.3a дополнен, комментарий с деталями — в issue #6.
Ветка docs/adr001-ltr-confirmed, PR https://github.com/Ssazurov/ds_search/pull/13


## gar-core-api#221: Discovery REST API (2026-09-07)
Затык из issue #16 (доступ в discovered_sources только через REST, не
напрямую в Postgres — паттерн ds_ingestion/gar_client) закрыт: реализован
Ssazurov/gar-core-api#221, PR https://github.com/Ssazurov/gar-core-api/pull/222.
5 эндпоинтов: POST/PATCH /search-runs, POST .../discovered-sources (bulk
upsert по url), GET /discovered-sources?status=&domain=,
PATCH /discovered-sources/{id}. Смок-тест через TestClient на реальной БД
прошёл. dictionary_suggestions endpoints не реализованы — вне скоупа #221.

## Issue #17: Probe-этап (частичная загрузка + скоринг)
Ветка feat/issue-17-probe-stage. Новый модуль src/discovery/:
- config.py — Settings (GAR_CORE_API_URL и т.п., по образцу gar_client/config.py)
- gar_client.py — тонкий REST-клиент к discovery API (#221): create/update
  search_run, upsert/list/update discovered_sources
- probe.py — `run_probe_stage()`: тянет discovered_sources status=new через
  клиент, для каждого URL — потоковый httpx GET с cap PROBE_MAX_BYTES
  (default 2МБ), `DefaultMarkdownGenerator.generate_markdown()` +
  переиспользованный `build_content_filter()`/`link_to_text_ratio()` из
  src/crawler/filters.py (ADR-001 п.3a) дают fit_markdown/LTR.
  `_score_from_content()`: None при thin content (<200 симв, SPA-случай —
  relevance_score не трогается, находка не отсеивается, ADR-002), 0.1 при
  LTR > LTR_THRESHOLD (каталог/листинг), иначе 0.5*длина+0.5*(1-LTR).
  Обновляет только relevance_score через PATCH — status находки (approve/
  reject) остаётся решением пользователя, probe его не меняет.
- tests/test_probe.py: 5 тестов (score для thin/catalog/substantive,
  probe_source на fake httpx.AsyncClient, run_probe_stage на fake
  GarDiscoveryClient) — py_compile + весь набор 21/21 passed.
Не проверено end-to-end по сети — gar-core-api не поднят как сервис
локально в этой сессии (только in-process TestClient при разработке #221).
Ещё не закоммичено/не запушено.


## Issue #18: Дедупликация находок
Ветка feat/issue-18-dedup. Новый src/discovery/dedup.py:
- loaded_document_urls(data_root) — нормализованные URL уже загруженных
  документов из data/raw/**/*.json с content_status=="saved" (issue #18 п.а)
- past_findings_urls(client) — нормализованные URL прошлых находок в
  статусах approved/rejected/downloaded через GET /discovered-sources
  (gar-core-api#221); эндпоинт не скоуплен по search_run_id — покрывает
  все прошлые прогоны, не только текущий (issue #18 п.б, ADR-002 п.6)
- mark_duplicates(candidates, known_urls) / dedup_candidates(...) —
  проставляют is_duplicate на кандидатах (dict url/title/snippet/...)
  через переиспользованный canonicalize_url() из src/crawler/filters.py
  ДО upsert в discovered_sources
tests/test_dedup.py: 5 тестов (loaded_document_urls saved-only/missing-root,
mark_duplicates, past_findings_urls все 3 статуса, dedup_candidates
локальный+удалённый источники) — py_compile + весь набор 26/26 passed.
Не закоммичено.


## Issue #19: Streamlit UI (справочники + поиск + результаты) — PR #53
Ветка feat/issue-19-streamlit-ui, закоммичено и запушено, PR #53 создан
(Closes #19), не смёржен.
- ui/app.py — 3 таба (Справочники/Поиск/Результаты)
- ui/dictionaries_tab.py — CRUD directions/doc_types/target_audiences/
  age_groups прямо в config/categories.yaml через новые
  src/metadata/schema.py:load_dictionaries()/save_dictionaries()
  (новый формат YAML с ключом directions; license_statuses — фикс. enum
  backend'а, не редактируется)
- ui/search_tab.py — запуск поиска через новый src/discovery/run_search.py
  (chain.search() -> dedup_candidates() -> upsert_discovered_sources()),
  пресеты через новый src/discovery/presets.py
  (config/search_presets.yaml)
- ui/results_tab.py — таблица discovered_sources
  (GarDiscoveryClient.list_discovered_sources), фильтры статус/домен/текст,
  дубли скрыты по умолчанию, bulk approve (лениво триггерит license-check
  через src/license/checker.py)/reject/queue
- requirements.txt: +streamlit, +pandas (не хватало — установлено и
  проверено импортом ui.app)
py_compile OK, pytest 29/29 (tests/test_run_search.py новый). UI НЕ
проверен через реальный `streamlit run` (нет браузера в этой сессии) —
только py_compile + import ui.app в bare-режиме.
На #20 оставлен комментарий: #19 был закрыт вручную без кода, теперь код
есть в PR #53.

## Issue #20: вкладки загрузка/документы/источники/дашборд — PR #54
Ветка feat/issue-20-upload-docs-sources-dashboard, закоммичено и запушено,
PR #54 создан (Closes #20), не смёржен. #19 (PR #53) уже смёржен в main.
- src/discovery/download.py — скачивание одной одобренной находки:
  один `AsyncWebCrawler.arun(url)` без deep-crawl (не SourceCrawler.run()),
  license-check, PDF-тизер/thin-content fallback переиспользован в
  компактном виде из crawler.py. tests/test_download.py: 7 тестов.
- ui/upload_tab.py — очередь (status=queued/error) с кнопкой "Скачать";
  ручная загрузка файла (обязательные метаданные, data/raw/manual/) или
  ссылки (создаётся как approved находка через gar_client, license-check
  выполнится при скачивании — issue #20 п.2 "стандартный пайп").
- ui/documents_tab.py — стадии raw/clean сканированием ФС. metadata/
  ingestion — всегда not_started (нет сигнала от ds_ingestion).
- ui/sources_tab.py — CRUD config/licenses.yaml (issue #3, не новая
  таблица) + агрегация discovered_sources по домену.
- ui/dashboard_tab.py — воронка found->approved->downloaded->ingested(=0),
  разбивка по направлениям, таблица ошибок.
- ADR-002: раздел "Уточнения 2026-09-07" (обоснование выше) + открытые
  вопросы 6 (dictionary_suggestions вне скоупа #221) и 7 (metadata/
  ingestion статус нужен от ds_ingestion — follow-up при необходимости).
py_compile + import ui.app (bare mode) OK, pytest 36/36 (было 29).

## Issue #21: keyword/BM25 классификатор direction/category/doc_type/audience
Ветка feat/issue-21-classifier. `src/discovery/classify.py` +
`config/classifier_keywords.yaml` — substring-count RU-ключевиков по
title+snippet, best-label или None (без гадания); direction выводится из
category через `directions` в categories.yaml. Интегрировано в
`run_search.py:_hit_to_candidate()` — suggested_* черновым значением на
каждую находку, явный `metadata` поиска (issue #19) приоритетнее.
tests/test_classify.py: 6 тестов. py_compile + pytest 43/43 (venv).
ADR-002 дополнен "п.6 финал". Не закоммичено/не запушено.

## Issue #6 (добивка): video-only детект + отчёт по отклонённым
Ветка feat/issue-6-content-cleaning. Осталось из issue #6 (thin-content/
LTR/content_status уже были реализованы ранее, PR #13):
- `filters.py: is_video_only_page()` — детект `<iframe>` youtube/vk/rutube/
  vimeo + короткий fit_markdown -> отдельный `content_status=
  rejected_video_only` (не путается с общим `rejected_thin_content`).
- `crawler.py` — вызов встроен в существующую ветку thin-content, до общего
  `rejected_thin_content` fallback; новый счётчик `skipped_video` в логе.
- `scripts/rejected_report.py` — агрегирует `data/raw/<source>/rejected/
  *.json` по `content_status` в `data/raw/<source>/rejected_report.md`
  (url, title, LTR/chars) для ручной проверки.
py_compile + pytest 43/43. Не прогнано на живых данных с реальным видео-URL
(нет video-страниц в текущем 10-документном корпусе downsideup).

## NEXT SESSION
Issue #21 и #20 (PR #54) уже смёржены в main. Issue #6 — PR готовится
(эта сессия). Дальше — Epic #44 (news block), начиная с #45 (news_items
таблица), либо follow-up issues из открытых вопросов ADR-002 п.6-7.

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

## 2026-09-10 — issue #43: тематические сессии (notebooks) по этапам

- `src/rag/sessions.py`: реализация тематических сессий (notebooks) — диалог
  привязывается к теме (этап/категория из information architecture), история
  сессий не смешивается между собой. `SessionTopic` валидирует
  `lifecycle_stage` по `LIFECYCLE_STAGES` и требует `lifecycle_stage` или
  `category`. `ThematicSession` хранит историю `SessionTurn` и снапшот
  `patient_profile` (наследуется при переключении темы, не теряется).
  `SessionStore` — in-memory реестр с общим профилем пользователя, который
  наследуется в каждую новую сессию; метод `switch()` создаёт пустую сессию в
  новой теме, сохраняя профиль, но не историю.
- `tests/test_rag_sessions.py`: 6 тестов — привязка к теме и наследование
  профиля, изоляция историй, переключение темы с сохранением профиля,
  валидация `lifecycle_stage`, требование темы, KeyError для пропущенной
  сессии. Проверка: focused pytest `6 passed`, `py_compile` и
  `git diff --check` — успешно.
- В `ds_search` нет экрана RAG-чата; `SessionStore` предназначается для
  будущего `/chat` endpoint'а или внешнего RAG-оркестратора (ds_site).

## 2026-09-10 — issue #42: уровень аудитории parent/specialist в system prompt

- `src/rag/response_modes.py`: добавлен параметр `audience: parent | specialist`
  в `build_system_prompt()` и `prepare_generation_request()`. `parent` добавляет
  инструкцию объяснять простым языком без сложной терминологии; `specialist` —
  использовать профессиональную терминологию и ссылаться на клинические
  рекомендации. Параметр независим от `response_mode`, не меняет retrieved chunks.
- `tests/test_rag_response_modes.py`: 5 новых тестов — простой язык для parent,
  терминология для specialist, независимость от response_mode, rejection未知ного
  значения, хранение в `GenerationRequest`.
- Проверка: focused pytest `16 passed`, `py_compile` и `git diff --check` —
  успешно.

## 2026-09-10 — issue #41: query decomposition для сложных вопросов

- `src/rag/query_decomposition.py`: эвристическая декомпозиция сложных вопросов
  на 2-5 под-запросов перед retrieval. `decompose_query()` возвращает
  `DecomposedQuery` с `original`, `sub_queries` и `decomposed`; для простых
  вопросов (менее 2 topic-marker'ов: союзы `и`/`или`/`а также`, `;`, запятые)
  возвращает исходный вопрос без изменений. Дубликаты под-запросов удаляются,
  количество ограничивается `max_sub_queries` (default 5).
- `tests/test_query_decomposition.py`: 34 теста — детекция сложности, сплит по
  разделителям, дедупликация, clamp, пустые входы, frozen dataclass.
  Проверка: focused pytest `34 passed`, `py_compile` и `git diff --check` —
  успешно.
- В `ds_search` пока нет экрана RAG-чата; `decompose_query()` предназначен
  для использования будущим `/chat` endpoint'ом или внешним RAG-оркестратором
  (ds_ingestion/ds_site) перед retrieval.

## 2026-09-10 — issue #40: экспорт ответа и диалога

- `src/rag/export.py`: чистый renderer поверх готового ответа/истории без
  повторного retrieval или generation. `export_answer()` и `export_dialogue()`
  поддерживают `pdf`, `markdown`/`md` и `text`/`txt`; в экспорт попадают вопрос,
  ответ и нормализованный список уникальных `source_url`.
- PDF рендерится через `reportlab` с Unicode-шрифтом; при отсутствии зависимости
  выбрасывается явный `PdfExportError`, Markdown и текст работают независимо.
  `requirements.txt` дополнен `reportlab>=4.0`.
- `tests/test_rag_export.py`: проверены источники, полная история, форматы,
  plain-text ссылки и валидация формата. Проверка: focused pytest `6 passed`,
  PDF-тест пропущен из-за отсутствующего `reportlab` в текущем `.venv`,
  `py_compile` успешен.
- В `ds_search` пока нет экрана RAG-чата; download-кнопки должны передать
  готовую историю в этот renderer на стороне будущего chat UI/API.

## 2026-09-09 — issue #39: follow-up вопросы после ответа

- `src/rag/response_modes.py`: system prompt требует после основного ответа
  предлагать отдельным списком ровно 2–3 коротких вопроса-продолжения,
  релевантных ответу и `patient_profile`; вопросы не должны повторять исходный
  запрос или содержать неподтверждённые факты.
- `tests/test_rag_response_modes.py`: добавлена проверка follow-up инструкции
  вместе с контекстом профиля.

## 2026-09-09 — issue #37: инлайн-цитирование источников

- `src/rag/response_modes.py`: system prompt требует ставить ссылку на
  `source_url` сразу после каждого проверяемого утверждения, запрещает
  выдумывать URL и отдельный список источников без инлайн-ссылок.
- `tests/test_rag_response_modes.py`: добавлена проверка требований к prompt.
- Проверка: focused pytest `5 passed`, `py_compile` и `git diff --check` —
  успешно.

## 2026-09-09 — issue #36: patient_profile в RAG-контракте

- `src/rag/patient_profile.py` валидирует профиль диагностической карты
  (возраст, пол, диагноз, сопутствующие состояния, этап) и фильтрует chunks по
  `lifecycle_stage`/`comorbidity_tags`; остальные поля остаются контекстом
  генерации и не используются для догадок.
- `src/rag/response_modes.py`: `prepare_generation_request()` и system prompt
  принимают `patient_profile`, сохраняя retrieved chunks неизменными при
  отсутствии retrieval-фильтров.
- Тесты: `tests/test_patient_profile.py` и существующие response-mode тесты —
  8 passed; `py_compile` и `git diff --check` — успешно.

## 2026-09-09 — issue #34: RAG response modes

- `src/rag/response_modes.py` adds the generation-side `response_mode`
  contract: `full` produces a detailed synthesis prompt, `summary` asks for
  concise bullets. Unknown values are rejected.
- `prepare_generation_request()` passes the retrieved chunk sequence through
  unchanged, so response mode changes only generation instructions and never
  retrieval.
- Tests: `tests/test_rag_response_modes.py` covers both prompts, retrieval
  invariance, and invalid-mode rejection.

## 2026-09-09 — issue #33: metadata information architecture

- `src/metadata/profile.py` централизует обязательные поля ADR-0002: `date_indexed`,
  `category`, `lifecycle_stage`, `comorbidity_tags`, `reviewed_by`; неизвестные
  значения жизненного этапа не угадываются и получают `unspecified`.
- Профиль подключён к crawler/download, ручной загрузке, экспорту glossary/links
  и публикации news; ручная загрузка и поиск позволяют выбрать категорию/этап.
- `config/categories.yaml` содержит справочник этапов жизненного пути;
  `schema.REQUIRED_FIELDS` обновлён под ADR-0002.
- Проверка: focused pytest — 28 passed, `py_compile` и `git diff --check` — успешно.

## 2026-09-09 — issue #33: локализация ADR-0002

- Перенесён `/home/vector/projects/ds/docs/adr/0002-rag-agent-capabilities.md`
  в `docs/adr/0002-rag-agent-capabilities.md` без содержательных изменений.
- В `docs/decisions.md` зафиксировано решение по `category`, `lifecycle_stage` и
  обязательным ingestion metadata: `source_url`, `license`, `date_indexed`,
  `category`, `lifecycle_stage`, `comorbidity_tags`, `reviewed_by`.
- Код не изменялся. Следующий bounded slice: роль ingestion реализует/проверяет
  заполнение этих полей; роль search использует `category`/`lifecycle_stage` в
  рамках issue #33.

## 2026-09-08 — issue #72: адаптивное распознавание структуры HTML→MD

- `src/crawler/structure.py`: профильный механизм выбора структуры по домену и
  DOM-нормализация заголовков на стандартной библиотеке Python; существующие
  `h1..h6` сохраняются, визуальные `<b>`-подзаголовки внутри `.sln-news-wrap`
  сайта `sindromlubvi.ru` преобразуются в семантические `h2`.
- `src/crawler/filters.py`: `AdaptiveMarkdownGenerator` передаёт нормализованный
  HTML в стандартный Crawl4AI Markdown generator; неизвестные домены остаются
  без изменений.
- Тесты: `tests/test_structure.py` (профиль домена, сохранение h1,
  визуальный подзаголовок, неизвестный источник).
- Проверка: `py_compile` и `git diff --check` прошли. Pytest заблокирован
  отсутствующей локальной зависимостью `crawl4ai`.

## 2026-09-08 — ручная загрузка `sindromlubvi.ru/o-sindrome/`

- Страница сохранена в `data/raw/basic/ds_o-sindrome2.md` и сопровождающем
  `ds_o-sindrome2.json`; направление `basic`, лицензия
  `attribution_required`.
- Для профиля `sindromlubvi.ru` подключено удаление контейнеров шапки,
  хлебных крошек, подвала и cookie-баннеров до HTML-to-Markdown-конвертации;
  основной `.sln-content` сохраняется.
- `use_container_width` заменён на `width="stretch"` в UI Streamlit.
- Проверки: `tests/test_structure.py` — `4 passed`; `py_compile` изменённых
  Python-модулей — успешно; `git diff --check` — успешно.

## 2026-09-08 — issue #69 реализован (CRUD справочников через UI)

- `ui/dictionaries_tab.py`: draft в `st.session_state`, CRUD направлений и
  категорий с переименованием, проверками при сохранении и подтверждением
  разрушительных операций; `license_statuses` и остальные справочники
  недоступны для редактирования.
- `src/metadata/schema.py`: общая проверка идентификаторов/структуры и
  атомарное сохранение через временный YAML, повторный `safe_load` и
  `os.replace`; при ошибке исходный файл и draft остаются без изменений.
  Неизвестные секции `categories.yaml` сохраняются.
- Тесты: `tests/test_metadata_schema.py`; focused result — `4 passed`.
- Полный `python3 -m pytest -q` заблокирован отсутствующей зависимостью
  `crawl4ai` в текущем окружении (ошибка collection в шести discovery/crawler
  тестах); изменённые модули успешно прошли `py_compile` и `git diff --check`.

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

## Issue #45: news_items — SQLite таблица + миграция — PR #57
Ветка feat/issue-45-news-table, закоммичено и запушено, PR #57 (Closes #45),
не смёржен. ADR-003 (новостной блок, весь пайплайн Epic #44) создан.
- `src/news/db.py`: SQLite `data/news.db` (не GAR Postgres — issue ADR-003).
  `init_db()` — CREATE TABLE IF NOT EXISTS (без Alembic), схема ровно по
  ТЗ #45 (source_url UNIQUE, status CHECK draft/published/rejected, tags/
  channels — JSON-массивы). `insert_news_item/get_news_item/
  list_news_items(status)/update_status` (published -> ставит published_at).
- `src/metadata/schema.py`: DIRECTIONS += "news", LICENSE_STATUSES +=
  "own_generated".
- tests/test_news_db.py: 7 тестов (init idempotent, insert/get, дубль
  source_url -> IntegrityError, фильтр по статусу, published_at, invalid
  status, missing item). pytest 50/50 (было 43).

## Issue #46: LLM-draft модуль — конфиг YAML + генерация черновика — PR #58
Ветка feat/issue-46-news-llm-draft.
- `config/news_llm.yaml` — provider(anthropic|openai_compatible)/model/
  endpoint/temperature/max_tokens/timeout_s/prompt_template (ADR-003).
- `src/news/llm_draft.py`: `load_llm_config()` (dataclass LlmConfig из YAML),
  `build_prompt()` (.format по source dict), `call_llm()` — диспатч по
  provider (`_call_anthropic` — messages API + ANTHROPIC_API_KEY,
  `_call_openai_compatible` — chat/completions + OPENAI_API_KEY), сырой
  httpx (без SDK — по образцу gar_client). `parse_llm_json()` — снимает
  markdown fence ```json, если модель всё же обернула ответ.
  `generate_draft(source, config=None)` — prompt->LLM->JSON->dict под
  `db.insert_news_item` (status=draft, requires_review=True, channels=[]
  — approve/публикация каналов в issue #48).
- tests/test_llm_draft.py: 6 тестов (prompt fill, parse plain/fenced/
  invalid, unknown provider, generate_draft с моком call_llm).
  py_compile OK, pytest 56/56 (было 50).
Не проверено на реальном API-ключе (нет ключа в этой сессии) — только
мок-тесты call_llm.

## 2026-09-08 — issue #48: Streamlit-страница «Новости» (ревью черновиков)
Ветка feat/issue-48-news-review-ui.
- `src/news/db.py`: добавлены `update_news_item(id, fields)` (частичный
  апдейт title/summary/body_md/tags/channels, неизвестные ключи
  игнорируются) и `delete_news_item(id)`.
- `ui/news_tab.py` — фильтр по статусу (draft/published/rejected/все),
  список по свежести (list_news_items уже ORDER BY created_at DESC),
  на каждый item — expander с инлайн-редактированием полей, кнопки
  Сохранить/Опубликовать (status=published)/Отклонить/Удалить.
  Публикация здесь — только смена статуса + выбор каналов (channels=
  ["telegram"]), сама доставка в ds_site/GAR — issue #49 (вне scope).
- `ui/app.py` — новая вкладка "Новости".
- tests/test_news_db.py: +5 тестов (update/delete/noop/unknown fields).
  pytest 60/60 (было 56). py_compile ui/news_tab.py + ui/app.py OK.
- Не проверено: `streamlit run` вживую (нет браузера в этой сессии).

## 2026-09-08 — issue #49: publish-адаптер news_items -> GAR ingestion
Ветка feat/issue-49-news-publish. ds_site (пустой репо, README: "свой
контент не хранит, данные через GAR API") — уточнение внесено в ADR-003:
публикация в ds_site == ingestion в GAR, отдельного push-API в сайт нет.
- `src/news/db.py`: миграция `gar_document_id`/`publish_error` (ALTER
  TABLE, best-effort — CREATE TABLE IF NOT EXISTS колонки не добавляет),
  `set_publish_result()`.
- `src/news/publish.py`: `GarNewsClient` (ensure_dataset/ingest_document,
  по образцу ds_ingestion/gar_client — не переиспользован напрямую, чужой
  репозиторий/пакет), `build_content_md()` (# title + body_md/summary),
  `build_metadata()` (doc_type=news, license=own_generated, direction,
  source_domain, keywords из tags, publish_date), `publish_news_item()` —
  идемпотентно (skip если gar_document_id уже есть, если не force),
  ошибка GAR пишется в publish_error и пробрасывается вызывающему.
- `scripts/publish_news.py` — CLI батч (`python -m scripts.publish_news
  [--force]`) для cron/бэкфилла уже published item без gar_document_id.
- `ui/news_tab.py`: кнопка "Опубликовать" теперь дергает publish_news_item
  сразу после update_status; кнопка "Переотправить в GAR" при ошибке;
  publish_error показывается в UI.
- ADR-003 дополнен разделом "Уточнение 2026-09-08".
- tests/test_news_publish.py: 9 тестов (build_content/build_metadata,
  happy path на fake-клиенте, идемпотентность, force, missing/wrong
  status, запись ошибки). pytest 70/70 (было 60).
Не проверено: реальный вызов gar-core-api /ingestion/documents (нет
поднятого сервиса в этой сессии) — только фейковый клиент в тестах.

## 2026-09-08 — issue #61: cron-пайплайн автосбора новостей
Ветка feature/issue-61-news-cron, поверх feat/issue-49-news-publish (#49
ещё не смёржен в main — нужен publish.py). Дубли #62/#63 закрыты, работал
#61 (более детальный).
- `src/news/collect.py`: `collect_news(chain, queries=None, max_results=None,
  ...)` — для каждого query из `config/news_search_queries.yaml` (или
  переданных явно): SearchProviderChain.search -> canonicalize_url ->
  дедуп по news_items.source_url (`db.source_url_exists`, до скачивания/
  LLM) -> discovery.download.download_single (переиспользован ради
  license-гейта check_license, ADR-001 п.3 — не входит в scope домены без
  ручной проверки ToS) -> прочитать fit_markdown -> llm_draft.generate_draft
  -> db.insert_news_item. Каждый источник обёрнут в try/except — сбой
  одного не роняет прогон (per-item счётчики: drafted/license_denied/
  download_failed/llm_failed/skipped_duplicate), сбой одного query
  (QuotaExceeded/любая ошибка) — тоже не роняет остальные query.
  НЕ пишет в discovered_sources/GAR (см. ADR-003 "Уточнение issue #61") —
  та очередь для ручной курации основного корпуса (ADR-002), у news своя
  дедуп-таблица.
- `src/news/db.py`: `source_url_exists()` — дешёвая проверка перед
  download+LLM (не тратить их на уже собранный источник).
- `config/news_search_queries.yaml`: список тем поиска + max_results_per_query
  (не хардкод, по аналогии с news_llm.yaml).
- `scripts/collect_news.py` — CLI (`python -m scripts.collect_news`),
  докстринг содержит пример строки crontab (1 раз/час).
- ADR-003 дополнен разделом "Уточнение 2026-09-08 (issue #61)", запись в
  docs/decisions.md.
- tests/test_news_collect.py: 7 тестов (happy path, дедуп до download,
  license_denied, download-ошибка не роняет прогон, LLM-ошибка не роняет
  прогон, QuotaExceeded одного query не роняет остальные, чтение YAML-конфига).
  pytest 77/77 (было 70).
- Найден и исправлен баг в процессе: `_collect_one` не передавал `db_path`
  в `db.insert_news_item` — запись уходила в дефолтный `data/news.db`
  вместо переданного вызывающим кодом пути; insert падал с "no such table"
  и по коду ошибочно засчитывался как "дубликат" (тесты это отловили).
Не проверено: реальный запуск с Tavily/crawl4ai (только фейковые chain/
download/generate_draft в тестах), сам crontab-job не установлен в систему.

## NEXT SESSION
Epic #44 (news block) полностью закрыт (#45/#46/#48/#49/#61). PR #60 (#49)
уже смёржен в main; остаётся смёржить PR #64 (#61), затем по желанию —
включить cron в реальный crontab на сервере.


## 2026-09-08: issue #25 (глоссарий/ссылки export)
Ветка feature/issue-25-glossary-links-export, PR #66, ADR-005.
- `scripts/export_glossary_links.py`: читает
  `~/ds/data/downsyndrome_glossary.xlsx` (лист «Глоссарий СД», 64 термина
  реально заполнены — заголовок листа «117» устарел; лист «IT» пропущен,
  не для паблика) и `~/ds/data/sites_ru_down_syndrome.xlsx` (126 из 137
  строк с name+url).
- Пишет `data/exports/glossary.json`, `data/exports/links.json` (плоский
  JSON для ds_site, не коммитятся — data/ в .gitignore, генерятся заново
  запуском скрипта).
- Пишет `data/raw/glossary/glossary.json+.md`, `data/raw/links/
  links.json+.md` — формат идентичен адаптеру ds_ingestion (issue #5):
  `license=own_generated`, `source_url=internal://ds_search/<slug>`,
  `direction=methodology`, `category=inclusion`, `doc_type=glossary`/
  `resource_directory` (новые значения добавлены в
  `config/categories.yaml`, backend не валидирует doc_type).
- Решение агрегировать в 2 документа (не 117+137 мелких) — см. ADR-005.
- Проверено: dry_run через `ds_ingestion.src.adapter.pipeline.run_adapter`
  на обоих source_dir — 0 skipped/failed.
Не сделано: реальная загрузка в GAR (нужен запущенный gar-core-api +
dataset_id), сам `ds_site` (репо пустое, ADR-004 ещё не реализован) —
экспортированный JSON лежит наготове под будущую сборку страниц.


## 2026-09-08 — issue #26/#28: публичный шлюз GAR (ADR-052 в gar-core-api)

Статус: код готов и запушен (gar-core-api PR #224), деплой-часть — ручные
шаги, не сделаны. #28 и #26 остаются открытыми.

- Обнаружено: `services/tenant_context.py` (gar-core-api) слепо доверяет
  клиентскому `X-User-ID` (`admin-` префикс = полный обход ACL) — так
  нельзя пускать наружу без изменений.
- Решение — ADR-052 (gar-core-api/docs/adr/052-public-gateway-cloudflare-tunnel.md):
  новые `routers/public.py` + `services/public_gateway.py` —
  `POST /public/chat`, `GET /public/documents/scope-tree`. Требуют
  `X-Public-Api-Key` (env `GAR_PUBLIC_API_KEY`, fail-closed 503 без него),
  игнорируют клиентские X-User-ID/X-Tenant-ID, всегда резолвятся в
  фиксированную личность `public-site-readonly` (ACL — только read на
  1 датасет, `scripts/seed_public_acl.py`).
- `docs/cloudflared/config.yml` (gar-core-api) — path-based ingress,
  наружу только `/public/*` и `/health`.
- Проверено локально: gar-core-api перезапущен, test_tenant_context.py +
  test_document_scope.py зелёные (9/9), `/public/documents/scope-tree`
  без ключа -> 503 (ожидаемо).
- Не сделано (ручные шаги, вне агента): cloudflared tunnel
  login/create/route dns, Cloudflare Zero Trust Access app + Service
  Token, генерация GAR_PUBLIC_API_KEY (в gar-core-api и в будущем
  ds_site), seed ACL на реальный dataset_id, `cloudflared tunnel run`.
- `ds_site` — репозиторий пока пустой (только README), хотя #24/#25
  закрыты в трекере без кода; #26 (proxy-код на стороне сайта) не
  начат — ждёт этих ручных шагов инфраструктуры.

## 2026-09-08 — issue #67: ручная закачка одной страницы (URL + папка + имя файла)

Статус: код готов, тесты зелёные (79/79), PR открыт.

- `src/discovery/download.py`: `download_single()` получил опциональные
  `dest_dir` (папка сохранения, относительно `data_root`, либо абсолютная —
  переопределяет `data_root/domain`) и `filename` (базовое имя вместо
  doc_id-хэша; санитизируется `_sanitize_filename` — только alnum/`-`/`_`,
  до 100 символов, unicode/кириллица сохраняется). Оба параметра обратно
  совместимы (default None = старое поведение).
- `ui/upload_tab.py`: новая секция «Скачать одну страницу по ссылке» во
  вкладке «Загрузка» — вызывает `download_single` напрямую (URL,
  направление, опц. папка/имя), без похода через discovered_sources/
  очередь gar-core-api (та ветка осталась для находок из «Поиска»).
- Тесты: `test_download_single_dest_dir_and_filename`,
  `test_sanitize_filename_strips_unsafe_chars` в `tests/test_download.py`.
- ADR не создавался — расширение существующего публичного API
  (`download_single`) обратной совместимости, без изменения архитектуры
  (ADR-002 п.4-5 "download_single, не SourceCrawler" остаётся в силе).

## 2026-09-08 — восстановление UI прямой загрузки

- В активной ветке `feature/issue-69-dictionaries-crud` восстановлена секция
  «Скачать одну страницу по ссылке» из issue #67. Она вызывает
  `download_single()` напрямую и снова отображается между очередью и
  «Ручной загрузкой».
- Причина пропажи — в этой ветке отсутствовали `_render_direct_download()` и
  его вызов; issue #72 эти файлы не изменял.

## 2026-09-08 — исправлена прямая загрузка страницы

- `src/discovery/download.py`: `download_single()` теперь принимает `dest_dir`
  и `filename` для ручной загрузки; оба значения ограничены `data/raw`, имя
  задаётся без расширения, а очередь сохраняет прежнюю схему домен/хэш.
- `tests/test_download.py`: добавлены проверки пользовательской папки/имени и
  отклонения абсолютных/выходящих за корень путей.

## 2026-09-08 — исправлено распознавание вопросов в sindromlubvi.ru

- Реальная разметка страницы «О синдроме Дауна» использует `.sln-asks > div >
  div`, а не `.sln-news-wrap`/`<b>`. Профиль `sindromlubvi.ru` теперь
  преобразует первый дочерний `div` с текстом, оканчивающимся на `?`, в `h2`.
- `AdaptiveMarkdownGenerator` подключён также к `download_single()`, поэтому
  прямая загрузка больше не обходит нормализацию структуры.
- Проверено: `tests/test_structure.py` — 3 passed; `py_compile` и
  `git diff --check` — успешно.
- Файл `data/raw/basic/ds_o-sindrome3.md` отсутствует в текущем checkout
  (в каталоге есть только `ds_o-sindrome.md` и `ds_o-sindrome2.md`), поэтому
  его содержимое не изменялось.

## 2026-09-09 — ADR-0002 перенесён для issue #33

- Root ADR `ds/docs/adr/0002-rag-agent-capabilities.md` перенесён без
  содержательных правок в `docs/adr/0002-rag-agent-capabilities.md`.
- Ссылочная запись добавлена в `docs/decisions.md`.
- Следующий implementation-ready slice: роль `coder` реализует issue #33,
  добавив metadata `category` и `lifecycle_stage` в контракт/пайплайн ds_search
  с тестами; архитектурные решения и scope зафиксированы в ADR-0002.

## 2026-09-09 — issue #38: явное сообщение о непокрытых источниками аспектах

- `src/rag/response_modes.py`: system prompt требует дословно сообщать
  «мои источники не содержат ответа», если retrieved-фрагменты не покрывают
  аспект вопроса; запрещено дополнять пробел общими знаниями или скрывать его.
- `tests/test_rag_response_modes.py`: добавлена проверка этого требования.

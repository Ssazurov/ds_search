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

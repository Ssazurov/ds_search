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

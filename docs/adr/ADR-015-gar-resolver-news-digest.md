# ADR-015: Генерация news/digest берёт модель из GAR resolver

**Статус:** принято  
**Дата:** 2026-09-30  
**Связано:** ds_search#423, gar-core-api#439 (зависимость), gar-core-api#436 (эпик)

## Контекст

Сейчас генерация черновиков новостей и пересказов (digest) напрямую обращается к провайдерам (Ollama/Anthropic/OpenAI-compatible) через конфигурацию `config/news_llm.yaml`. Модель, эндпоинт и API-ключи хардкодятся на стороне ds_search.

gar-core-api#436 вводит централизованный resolver моделей: профили провайдеров, правила выбора модели по назначению (`purpose=chat|news|digest`) и размеру входа (`input_chars`). Для `digest` из больших статей — большая модель; для `news` — локальная.

Задача ds_search#423 — интегрировать `src/news/llm_draft.py` с GAR resolver вместо прямых вызовов провайдеров.

## Решение

1. **Новый API-эндпоинт в gar-core-api** (gar-core-api#439):  
   - `POST /generate` — полная генерация: принимает `purpose` (`news|digest`), `input_chars` (размер текста источника), `prompt`; возвращает сгенерированный текст.  
   - `GET /resolve?purpose=...&input_chars=...` (опционально) — resolver без генерации: возвращает выбранный профиль и модель.

2. **Интеграция в ds_search**:  
   - `src/gar_ingest/client.py`: добавить методы `GarIngestClient.generate(purpose, input_chars, prompt)` и опционально `resolve(purpose, input_chars)`.  
   - `src/news/llm_draft.py`:  
     - В `call_llm()` сначала попытка вызвать `GarIngestClient.generate(purpose, input_chars, prompt)`.  
     - При недоступности GAR (сетевая ошибка, 503) — fallback на локальные провайдеры из `news_llm.yaml` (существующая логика `_call_ollama`/`_call_anthropic`/`_call_openai_compatible`).  
     - `purpose` = `"news"` для обычных новостей, `"digest"` для пересказов (fmt="digest").  
     - `input_chars` = длина `source["text"]` после `clean_article_text()`.

3. **Конфигурация `news_llm.yaml`**:  
   - Остаются промпты (`prompt_template`, `prompt_template_digest`) и лимиты (`max_tokens`, `num_ctx`).  
   - Блок `provider`/`model`/`endpoint`/`api_key` — fallback, если GAR недоступен.  
   - Комментарий в файле: «Провайдер выбирается через GAR resolver (ADR-015); локальная конфигурация — fallback при недоступности GAR».

4. **Авторизация**:  
   - Используется сервисный API-ключ из `GAR_API_KEY` (env-переменная, как в `gar_ingest/client.py`).  
   - **Не** read-only ingest-клиент: `/generate` может быть защищён отдельным ACL-правилом.  
   - См. gar-core-api ADR-056 (сервисный API-ключ).

5. **Fallback-логика**:  
   - GAR resolver недоступен (сеть, 503, таймаут) → локальный провайдер из `news_llm.yaml`.  
   - GAR resolver вернул 422/400 (некорректный `purpose` или правило не найдено) → ошибка, не fallback (это конфигурационная проблема GAR).

## Последствия

**Плюсы:**
- Централизованное управление моделями: смена провайдера/модели в GAR admin UI без правки `news_llm.yaml` и пересборки ds-search.
- Единая логика выбора модели для всех потребителей (ds_search, gar-core-api chat_service, evaluation).
- Для digest из больших статей — автоматический выбор большой модели по правилу `input_chars > N`.

**Минусы:**
- Зависимость от доступности GAR: если GAR упал, генерация новостей откатывается на локальный Ollama.
- Промпты остаются на стороне ds_search (в `news_llm.yaml`): централизация промптов — вне scope этого ADR.

**Риски:**
- При fallback на локальный провайдер модель может отличаться от настроенной в GAR → разное качество генерации. Логировать факт fallback.
- Таймаут `/generate` должен быть достаточным для медленных моделей (Ollama 14B на CPU): 240с сейчас, оставить без изменений; в GAR — настраивается в профиле провайдера.

## Альтернативы

1. **Оставить прямые вызовы провайдеров** — отклонено: дублирование логики выбора модели, нет централизованного управления.
2. **Переместить промпты в GAR** — отложено: промпты news/digest специфичны для ds_search, централизация усложнит итерацию над формулировками.
3. **Синхронный fallback на каждый запрос** (попытка GAR → fallback) — принято: генерация новостей не критична по latency (фоновый cron), допустима задержка на сетевую попытку + fallback.

## Связанные решения

- gar-core-api ADR-056: сервисный API-ключ для межсервисных вызовов.
- gar-core-api#436: профили провайдеров, resolver по назначению и размеру входа.
- ds_search#419/#420: формат digest, промпт `prompt_template_digest`.

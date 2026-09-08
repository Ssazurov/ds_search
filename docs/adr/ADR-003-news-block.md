# ADR-003: Новостной блок — хранение и пайплайн

Дата: 2026-09-08. Статус: принято. Эпик: #44.

## Контекст
Нужен блок новостей (СД/РАС) с LLM-черновиками, ручной модерацией и
публикацией в ds_site + GAR RAG-корпус.

## Решение
- Хранилище: отдельная SQLite `ds_search/data/news.db` (не GAR Postgres —
  во избежание конфликтов alembic-цепочки GAR и лишней связанности).
- Таблица `news_items`: id, source_url (unique), source_name,
  source_published_at, title, summary, body_md, direction="news", tags
  (JSON-массив), requires_review (bool), status (draft|published|rejected),
  channels (JSON-массив), created_at, published_at.
- Новые значения enum: `direction="news"` (src/metadata/schema.py
  DIRECTIONS), `license="own_generated"` (LICENSE_STATUSES) — новости
  генерируются LLM на основе источника, не копируются как есть.
- Конфиг LLM вынесен в `config/news_llm.yaml` (provider/model/endpoint/
  temperature/prompt_template) — не хардкод в коде (issue #46).
- Пайплайн: cron-сбор → LLM-черновик → ручное approve в Streamlit
  (issue #48) → publish-адаптер в ds_site + ingestion в GAR как
  `doc_type=news` (issue #49).
- Telegram — целевой канал публикации; MAX отложен (нужно юрлицо).
- Админка — не новый сервис, страница в существующем Streamlit-приложении
  `ds_search/ui/` (единый инструмент, см. принцип "не плодить UI").

## Альтернативы
- Postgres/GAR-таблица — отклонено: чужая alembic-цепочка, лишняя связность
  с продуктом 1 в момент, когда схема ещё не стабилизировалась.
- Отдельный Node/FastAPI сервис под новости — отклонено: overhead ради
  MVP, Streamlit уже покрывает admin-flow остального проекта.

## Уточнение 2026-09-08 (issue #49)
"Публикация в ds_site" технически сводится к ingestion в GAR: ds_site
(см. ds_site/README.md) свой контент не хранит, читает материалы через
GAR API/RAG — как только новость проиндексирована с `doc_type=news`, она
видна сайту тем же путём, что и остальной корпус. Отдельный push-запрос
в ds_site API не нужен и не реализовывался. `news_items` получил колонки
`gar_document_id`/`publish_error` (идемпотентность/диагностика).

## Последствия
- SQLite-файл живёт в data/ (не в git, см. .gitignore data/).
- Миграции — простые `CREATE TABLE IF NOT EXISTS` в коде (issue #45),
  без Alembic — объём схемы не оправдывает инструмент миграций.

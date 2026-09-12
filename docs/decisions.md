# Журнал архитектурных решений

| Дата | ADR | Суть |
|------|-----|------|
| 2026-08-23 | ADR-001 | MVP: сателлиты GAR (не отдельный RAG-стек), Docling вместо PyMuPDF, license/ToS-проверка перед скачиванием, КонсультантПлюс/ГАРАНТ исключены, cron-оркестрация. |
| 2026-08-26 | ADR-002 | Discovery+курация вместо полного автокраулинга: поиск через Search API (не скрапинг SERP), таблица `discovered_sources`, probe-этап (частичная загрузка + LTR-скоринг), Streamlit UI (не Next.js) для курации находок, ручная загрузка, полное скачивание только после approve. Автокраулинг остаётся опциональным батч-режимом, не основным путём. |
| 2026-09-08 | ADR-003 | Новостной блок: таблица `news_items` в отдельной SQLite (не GAR Postgres), enum `direction="news"`/`license="own_generated"`, конфиг LLM в YAML, модерация в существующем Streamlit, публикация в ds_site + GAR (`doc_type=news`). |
| 2026-09-08 | ADR-003 (issue #61) | Cron-автосбор новостей не пишет в discovered_sources/GAR (та очередь — для ручной курации основного корпуса, ADR-002); переиспользует discovery.download.download_single (тот же license-гейт), дедуп по своей news_items. |
| 2026-09-08 | ADR-005 | Экспорт glossary/links xlsx -> JSON для ds_site + 2 агрегированных документа (не поштучно) в RAG, license=own_generated, source_url=internal://, новые doc_type glossary/resource_directory в categories.yaml. |
| 2026-09-07 | ADR-0002 | Возможности RAG-агента: агрегатор, режимы ответа, диагностическая карта и обязательные metadata `category`/`lifecycle_stage`; перенесено из root `ds/docs/adr/0002-rag-agent-capabilities.md`. |
| 2026-09-12 | амендмент ADR-001 п.2 / ADR-002 п.2 | Уточнение направления синхронизации схемы metadata-fields: источник правды — GAR (`sindrom-dauna`), редактируется только там; `ds_search/config/categories.yaml` и `ensure_domain_schema` (ds_ingestion) — локальная копия/bootstrap, не канал записи в GAR. Найдено при разборе alisa-i-chudesa.json (см. CURRENT_STATUS ds_search 2026-09-12). |

| 2026-09-12 | ADR-006 | Ingestion обычных документов в GAR через UI (не только новости): общий `GarIngestClient` (рефакторинг из news/publish.py), ingestion одного/пакета документов из `data/raw`, статус в sidecar `.json` (`gar_document_id`), дашборд считает «В GAR» по факту — закрывает ADR-002 п.7. `ds_ingestion` CLI остаётся для bulk/bootstrap. |

| 2026-09-12 | ADR-007 (issue #110) | Автозаполнение GAR-поля keywords — отдельный фоновый джоб `src/metadata/keywords_worker.py` ПОСЛЕ ingestion (не в pre-upload download.py/classify.py): читает indexed-документы через `GarIngestClient.list_documents`/`get_document_text`, извлекает keywords LLM'ом (`config/keywords_llm.yaml`), пишет `patch_document_metadata` (сервер мержит). Идемпотентно (skip если keywords уже есть), `--force`/`--dry-run`. |

## 2026-09-08 — ADR-052 (gar-core-api): публичный шлюз для сайта
Не автономное ADR ds_search (репозиторий gar-core-api ведёт свою нумерацию
ADR). Решение: Cloudflare Tunnel с path-based ingress (только /public/*,
/health) + Cloudflare Access Service Token + отдельный секрет
X-Public-Api-Key на уровне приложения, т.к. текущий tenant_context.py
слепо доверяет X-User-ID (admin- префикс = обход ACL) — публиковать как
есть было небезопасно. См. gar-core-api/docs/adr/052-public-gateway-cloudflare-tunnel.md,
gar-core-api PR #224, ds_search issue #28.

# ADR-013: GAR — единственный источник справочников; русские labels в UI

- Статус: принято (2026-09-24)
- Репо: ds_search

## Контекст
Источник правды по direction/category/age/doc_type и др. — GAR (датасет `sindrom-dauna`, `GET /datasets/{id}/metadata-fields`). У каждой опции есть `value` (slug) и `label` (русское название).
Сейчас UI держит локальную копию `config/categories.yaml`: вкладка «Справочники» её редактирует, `sync_from_gar` перезаписывает вручную и **теряет labels**. Итог: в selectbox видны slug'и (`zdorove`), локальные правки расходятся с GAR и затираются.

## Решение
1. Правки справочников делаются только в GAR. Вкладка «Справочники» в ds_search — read-only + кнопка «Обновить из GAR».
2. `load_dictionaries()` берёт данные из `gar_schema` (кэш `gar_schema_cache.json`, TTL 24ч, принудительное обновление кнопкой); `categories.yaml` — только офлайн-фолбэк, `sync_from_gar` сохраняет и labels.
3. Единый хелпер `label_of(field, value)` (fallback — сам value) + `format_func` во всех `st.selectbox`, фильтрах и таблицах (Загрузка, Поиск, Результаты, Документы, Материалы, Новости, Источники).
4. В метаданных документов, RAG и GAR по-прежнему хранится `value` (slug); меняется только отображение.

## Последствия
- Нет двойного редактирования и рассинхрона; русские названия везде.
- Без доступа к GAR UI работает на кэше/`categories.yaml` (slug при отсутствии label).
- Затронуто: `src/metadata/{gar_schema,schema,sync_from_gar}.py`, `ui/*_tab.py`, `ui/dictionaries_tab.py`.

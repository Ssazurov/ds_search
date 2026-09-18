# ds_search

Код для поиска и сбора материалов из интернета (дискавери-пайплайн для GAR).

## Запуск

Двойной клик по `run_site.bat` — поднимет Streamlit UI (WSL, venv `.venv`)
на http://localhost:8501.

Вручную:
```
wsl.exe bash -lc "cd /home/vector/projects/ds/ds_search && .venv/bin/streamlit run ui/app.py"
```

## Структура

- `src/search/` — поиск источников (Tavily)
- `src/discovery/` — probe, download, classify, dedup
- `ui/` — вкладки Streamlit (Поиск, Загрузка, Источники, Документы, Словари, Дашборд, Новости)
- `config/` — словари классификатора и категорий
- `tests/` — pytest
- `docs/adr/` — архитектурные решения

## Вкладка «Загрузка»

Кроме очереди из «Поиска» (discovered_sources → gar-core-api), есть ручная
закачка одной страницы по ссылке: URL + опционально папка назначения и
имя файла (`src/discovery/download.py:download_single`).

Подробности — `CURRENT_STATUS.md`.

### Неизвестный домен и ручная проверка ToS

Перед скачиванием конкретной страницы `download_single` проверяет `robots.txt`
и реестр `config/licenses.yaml`. Если домена нет в реестре, скачивание
останавливается со статусом `pending_manual_review`.

Порядок действий в UI:

1. Откройте вкладку «Источники / домены».
2. Добавьте домен без протокола и пути, например `sindromlubvi.ru`.
3. После ручной проверки ToS выберите статус:
   - `attribution_required` — консервативный вариант, если разрешение на
     использование материалов не подтверждено явно;
   - `allow` — только при подтверждённом праве на использование;
   - `deny` — если скачивание запрещено.
4. Для `attribution_required` задайте шаблон, например:
   `Источник: {title} ({source_url}), Синдром любви (sindromlubvi.ru)`.
5. В заметках сохраните результат проверки, включая ограничения
   `robots.txt`, затем нажмите «Сохранить».
6. Вернитесь во вкладку «Загрузка» и повторите скачивание.

Пример для страницы `https://sindromlubvi.ru/o-sindrome/`: текущий
`robots.txt` разрешает HTML-страницу `/o-sindrome/`, но запрещает прямые
PDF-файлы. Если явное разрешение на перепубликацию не найдено, используйте
`attribution_required` и сохраняйте атрибуцию в метаданных документа.

Не переводите неизвестные домены автоматически в `allow`: это отключает
обязательную ручную проверку ToS. Для одноразового использования можно
сохранить ссылку без скачивания, если нужен только зафиксированный источник.

## GAR-пользователи (X-User-ID)

ds_search обращается к gar-core-api под разными identity, у каждой — свой ACL
на датасете (`acl_rules` в gar-core-api):

- `ds-search-news-publish` — публикация новостей (`gar_ingest/client.py`),
  нужен `write`. ACL закреплён в `gar-core-api/scripts/seed_dataset_acl.py`.
- `admin-ds-ingestion` — ingestion-пайплайн (используется ds_ingestion), `write`/`manage`.
- `admin-ui` — чтение метаданных для ds_site/admin.
- `public-site-readonly` — публичное read-only чтение (`seed_public_acl.py`).

В `deploy/docker-compose.yml` сервис `ds-search` использует общий
`env_file: ./ds-ingestion.env`, поэтому для него обязателен явный override
`environment: GAR_USER_ID=ds-search-news-publish` — иначе наследуется
`ds-ingestion-adapter` из общего env-файла (см. ds_search#185). Другие
сервисы стека (`gar-core-api`, `gar-admin-ui`, `ds-site`) используют
отдельные `.env`-файлы и такому риску не подвержены.

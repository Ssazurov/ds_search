#!/bin/bash
set -e
cd /home/vector/ds/ds_search
git commit -m "feat(news): news_items SQLite table + migration (#45)

- src/news/db.py: init_db/insert/get/list/update_status, CHECK(status)
- direction=\"news\", license=\"own_generated\" в src/metadata/schema.py
- ADR-003 + docs/decisions.md
- tests/test_news_db.py (7 тестов)

Closes #45"
git push -u origin feat/issue-45-news-table

#!/bin/bash
set -e
cd /home/vector/ds/ds_search
gh pr create --title "feat(news): news_items SQLite table + migration" \
  --body "Closes #45

- src/news/db.py: init_db (CREATE TABLE IF NOT EXISTS, без Alembic), insert_news_item, get_news_item, list_news_items(status), update_status
- direction=\"news\" (DIRECTIONS), license=\"own_generated\" (LICENSE_STATUSES) в src/metadata/schema.py
- ADR-003 + docs/decisions.md
- tests/test_news_db.py: 7 тестов (init idempotent, insert/get, unique source_url -> IntegrityError, list по статусу, published_at, invalid status, missing item)
- pytest 50/50 (было 43), py_compile OK" \
  --base main --head feat/issue-45-news-table

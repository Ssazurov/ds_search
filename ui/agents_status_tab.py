"""Статус агентов — последние search-runs, агрегаты discovered_sources по
статусу, последний news_item + счётчик новостей за сегодня (issue #134)."""
from __future__ import annotations

from collections import Counter
from datetime import date

import streamlit as st

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from src.news.db import list_news_items


def render() -> None:
    st.header("Статус агентов")

    settings = load_settings()
    try:
        with GarDiscoveryClient(settings) as client:
            runs = client.list_search_runs(limit=20)
            sources = client.list_discovered_sources()
    except Exception as exc:  # noqa: BLE001
        st.error(f"gar-core-api недоступен: {exc}")
        return

    st.subheader("Последние search-runs")
    if runs:
        st.dataframe(
            [{
                "query": r.get("query", ""),
                "provider": r.get("provider") or "—",
                "status": r.get("status", ""),
                "result_count": r.get("result_count", 0),
                "started_at": r.get("started_at", ""),
                "completed_at": r.get("completed_at") or "—",
                "error": r.get("error") or "",
            } for r in runs],
            hide_index=True, width="stretch",
        )
    else:
        st.info("Search-runs ещё не запускались")

    st.subheader("Discovered sources по статусу")
    status_counts = Counter(s.get("status", "new") for s in sources)
    if status_counts:
        st.bar_chart(status_counts)
    else:
        st.info("Источников пока нет")

    st.subheader("Новости")
    try:
        news_items = list_news_items()
    except Exception as exc:  # noqa: BLE001
        st.error(f"news.db недоступна: {exc}")
        return

    today = date.today().isoformat()
    today_count = sum(1 for n in news_items if (n.get("created_at") or "").startswith(today))
    c1, c2 = st.columns(2)
    c1.metric("Всего новостей", len(news_items))
    c2.metric("За сегодня", today_count)

    if news_items:
        last = news_items[0]
        st.caption(
            f"Последняя: «{last.get('title', '')}» "
            f"({last.get('status', '')}, {last.get('created_at', '')})"
        )
    else:
        st.info("Новостей пока нет")

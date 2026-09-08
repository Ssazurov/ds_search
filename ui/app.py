"""Streamlit UI ds_search (issue #19, ADR-002 п.3-4 финал).

Запуск: streamlit run ui/app.py
Требует GAR_CORE_API_URL (доступ к discovery API, gar-core-api#221) и
TAVILY_API_KEY для вкладки "Поиск".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from ui import (
    dashboard_tab, dictionaries_tab, documents_tab, news_tab, results_tab,
    search_tab, sources_tab, upload_tab,
)

st.set_page_config(page_title="ds_search — discovery", layout="wide")
st.title("ds_search — discovery & курация")

tabs = st.tabs([
    "Справочники", "Поиск", "Результаты", "Загрузка", "Документы", "Источники", "Дашборд", "Новости",
])
with tabs[0]:
    dictionaries_tab.render()
with tabs[1]:
    search_tab.render()
with tabs[2]:
    results_tab.render()
with tabs[3]:
    upload_tab.render()
with tabs[4]:
    documents_tab.render()
with tabs[5]:
    sources_tab.render()
with tabs[6]:
    dashboard_tab.render()
with tabs[7]:
    news_tab.render()

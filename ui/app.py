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

from ui import dictionaries_tab, results_tab, search_tab

st.set_page_config(page_title="ds_search — discovery", layout="wide")
st.title("ds_search — discovery & курация")

tab_dict, tab_search, tab_results = st.tabs(["Справочники", "Поиск", "Результаты"])
with tab_dict:
    dictionaries_tab.render()
with tab_search:
    search_tab.render()
with tab_results:
    results_tab.render()

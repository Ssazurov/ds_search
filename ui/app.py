"""Streamlit UI ds_search (issue #275: UI-полировку).

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
    agents_status_tab, dashboard_tab, dictionaries_tab, documents_tab,
    materials_tab, news_tab, results_tab, search_tab, site_publish_tab, sources_tab,
    upload_tab,
)

# Название сайта — «Солнечный мир» (см. ds_site/app/layout.tsx).
# Админка Streamlit — курация материалов этого сайта.
st.set_page_config(page_title="Солнечный мир (администрирование)", layout="wide")
st.title("Солнечный мир — администрирование материалов")

# Отступ сверху: уменьшаем padding-top block-container в 2 раза
# (Streamlit дефолт 5rem -> 2.5rem), чтобы контент не «парил» под хедером.
st.markdown(
    """
    <style>
      div.block-container { padding-top: 2.5rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

TABS = [
    "Справочники", "Поиск", "Результаты", "Загрузка", "Документы", "Источники",
    "Дашборд", "Новости", "Материалы", "Статус агентов", "Внешний сайт",
]

_RENDER = {
    "Справочники": dictionaries_tab.render,
    "Поиск": search_tab.render,
    "Результаты": results_tab.render,
    "Загрузка": upload_tab.render,
    "Документы": documents_tab.render,
    "Источники": sources_tab.render,
    "Дашборд": dashboard_tab.render,
    "Новости": news_tab.render,
    "Материалы": materials_tab.render,
    "Статус агентов": agents_status_tab.render,
    "Внешний сайт": site_publish_tab.render,
}

# Запоминание открытой вкладки (issue #275).
#
# ВАЖНО: st.tabs() принципиально не подходит для этого — у него нет параметра
# для программного выбора активной вкладки, а его внутренняя DOM-разметка
# (BaseWeb) — деталь реализации, которая меняется между версиями Streamlit;
# JS-хаки поверх неё (клики по data-baseweb="tab" через components.v1.html)
# трижды не сработали из-за гонок/несовпадения разметки. Вместо этого
# используем st.segmented_control — управляемый Python-виджет, чьё состояние
# задаётся через st.session_state без единой строчки JS.
_qp_tab = st.query_params.get("tab")
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = _qp_tab if _qp_tab in TABS else TABS[0]

selected = st.segmented_control(
    "Раздел",
    TABS,
    key="active_tab",
    label_visibility="collapsed",
)

# selection_mode по умолчанию "single" — повторный клик по уже выбранному
# пункту снимает выбор (вернёт None). В этом случае остаёмся на последней
# известной вкладке, не трогая ключ виджета (Streamlit запрещает менять
# st.session_state виджета после его инстанцирования в этом же прогоне).
active = selected if selected is not None else st.session_state.get("_last_active_tab", TABS[0])
st.session_state["_last_active_tab"] = active

if st.query_params.get("tab") != active:
    st.query_params["tab"] = active

_RENDER[active]()

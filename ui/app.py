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
    news_tab, notify, results_tab, search_tab, site_publish_tab, sources_tab,
    upload_tab,
)
from ui.theme import inject_theme, sidebar_brand, topbar

# Название сайта — «Солнечный мир» (см. ds_site/app/layout.tsx).
# Админка Streamlit — курация материалов этого сайта.
st.set_page_config(page_title="Солнечный мир", layout="wide")
inject_theme()  # GAR-стиль: шрифты IBM Plex, отступы (issue #504)

TABS = [
    "Справочники", "Поиск", "Результаты", "Загрузка", "Документы", "Новости",
    "Источники", "Дашборд", "Статус агентов", "Внешний сайт",
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
    "Статус агентов": agents_status_tab.render,
    "Внешний сайт": site_publish_tab.render,
}

# Запоминание открытой вкладки (issue #275). Виджет навигации — st.radio в
# боковом меню (issue #504); его состояние задаётся через session_state без JS.
_qp_tab = st.query_params.get("tab")
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = _qp_tab if _qp_tab in TABS else TABS[0]

# Навигация — боковое меню (issue #504). st.radio всегда отдаёт выбранное
# значение, поэтому «запоминание последней вкладки» больше не нужно.
# Состояние — в session_state (без JS), стартовая вкладка — из ?tab=.
sidebar_brand()
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = TABS[0]


def _go(tab: str) -> None:
    st.session_state["active_tab"] = tab


active = st.session_state["active_tab"]
for _i, _t in enumerate(TABS):
    st.sidebar.button(_t, key=f"navon_{_i}" if _t == active else f"nav_{_i}",
                      on_click=_go, args=(_t,), use_container_width=True)
topbar(active)
# notify.py читает последнюю активную вкладку для сообщений слота.
st.session_state["_last_active_tab"] = active

if st.query_params.get("tab") != active:
    st.query_params["tab"] = active

# Slot для сообщений (issue #366): создаём контейнер до рендера вкладки,
# чтобы сообщения, добавленные во время рендера, появились вверху.
slot = st.container()
with st.container(key="tabsrc" if active == "Источники" else "tabgen"):
    _RENDER[active]()
with slot:
    notify.render_messages(active)

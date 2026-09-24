"""Streamlit UI ds_search (issue #275: UI-полировку).

Запуск: streamlit run ui/app.py
Требует GAR_CORE_API_URL (доступ к discovery API, gar-core-api#221) и
TAVILY_API_KEY для вкладки "Поиск".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from streamlit.components.v1 import html

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
TABS_BY_NAME = {name: idx for idx, name in enumerate(TABS)}


def _sync_tab_js() -> None:
    """Синхронизирует открытую вкладку с query-параметром `tab`.

    При переключении вкладки JS пишет имя активной вкладки в URL
    (`history.replaceState`), Streamlit перезапускает скрипт и при старте
    (ниже) читает `tab` из query params — так при обновлении страницы
    открывается последняя активная вкладка.
    """
    html(
        """
        <script>
        (function () {
          const names = %s;
          function currentTabName() {
            const btns = parent.document.querySelectorAll('[data-baseweb="tab"]');
            for (const b of btns) {
              if (b.getAttribute("aria-selected") === "true") {
                const i = Array.from(btns).indexOf(b);
                return names[i] || null;
              }
            }
            return null;
          }
          function writeUrl(name) {
            if (!name) return;
            const u = new URL(location.href);
            u.searchParams.set("tab", encodeURIComponent(name));
            history.replaceState(null, "", u.toString());
          }
          // при клике на вкладку — обновить URL (регистрируем до восстановления
          // ниже, чтобы клик из restoreFromUrl тоже сработал через тот же путь).
          // Флаг на window — чтобы не плодить обработчики при каждом rerun.
          if (!parent.window.__dsTabSyncBound) {
            parent.window.__dsTabSyncBound = true;
            parent.document.addEventListener("click", function (e) {
              const t = e.target.closest('[data-baseweb="tab"]');
              if (!t) return;
              const btns = parent.document.querySelectorAll('[data-baseweb="tab"]');
              const i = Array.from(btns).indexOf(t);
              writeUrl(names[i] || null);
            });
          }
          // Восстановление вкладки из URL при загрузке/обновлении страницы:
          // st.tabs не умеет открывать вкладку по индексу программно, поэтому
          // симулируем клик по нужной кнопке вкладки.
          const params = new URLSearchParams(location.search);
          const raw = params.get("tab");
          let restored = false;
          if (raw) {
            let wanted;
            try { wanted = decodeURIComponent(raw); } catch (e) { wanted = raw; }
            const idx = names.indexOf(wanted);
            if (idx >= 0) {
              const btns = parent.document.querySelectorAll('[data-baseweb="tab"]');
              const target = btns[idx];
              if (target && target.getAttribute("aria-selected") !== "true") {
                target.click();
                restored = true;
              }
            }
          }
          if (!restored) {
            writeUrl(currentTabName());
          }
        })();
        </script>
        """ % json.dumps(TABS),
        height=0,
    )


# 1. Восстановление открытой вкладки при старте/обновлении.
active_name = st.query_params.get("tab") or "Справочники"
active_idx = TABS_BY_NAME.get(active_name, 0)

tabs = st.tabs(TABS)
_sync_tab_js()

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

for idx, name in enumerate(TABS):
    with tabs[idx]:
        _RENDER[name]()
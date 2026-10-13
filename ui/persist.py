"""Запоминание выбора в URL (переживает F5): вкладки st.tabs любой вложенности."""
import streamlit as st


def tabs(names, key):
    """st.tabs, чей выбор хранится в ?<key>=<вкладка>. key — уникальное имя параметра."""
    names = list(names)

    def _sync():
        st.query_params[key] = st.session_state[key]

    kw = {}
    cur = st.session_state.get(key) or st.query_params.get(key)
    if cur in names:
        kw["default"] = cur
    return st.tabs(names, key=key, on_change=_sync, **kw)

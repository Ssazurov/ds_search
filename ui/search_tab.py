"""Параметры поиска — запуск search_run + пресеты (issue #19 п.2)."""
from __future__ import annotations

import streamlit as st

from src.discovery.presets import delete_preset, load_presets, save_preset
from src.discovery.run_search import run_search
from src.metadata.schema import load_dictionaries
from src.metadata.profile import LIFECYCLE_STAGES
from src.search.base import QuotaExceeded
from src.search.chain import SearchProviderChain
from src.search.tavily import TavilyProvider

_NONE = "— не выбрано —"


def _build_chain() -> SearchProviderChain:
    return SearchProviderChain([TavilyProvider()])


def render() -> None:
    st.header("Параметры поиска")
    dictionaries = load_dictionaries()
    presets = load_presets()
    preset_names = [_NONE] + [p["name"] for p in presets]

    chosen = st.selectbox("Пресет", preset_names, key="preset_select")
    preset = next((p for p in presets if p["name"] == chosen), {}) if chosen != _NONE else {}

    query = st.text_input("Тема поиска", value=preset.get("query", ""))
    direction = st.selectbox(
        "Направление", [_NONE] + list(dictionaries["directions"].keys()),
        index=(list(dictionaries["directions"].keys()).index(preset["direction"]) + 1
               if preset.get("direction") in dictionaries["directions"] else 0),
    )
    categories = dictionaries["directions"].get(direction, []) if direction != _NONE else []
    category = st.selectbox("Категория", [_NONE] + categories)
    target_audience = st.selectbox(
        "Целевая аудитория", [_NONE] + dictionaries["target_audiences"],
        index=(dictionaries["target_audiences"].index(preset["target_audience"]) + 1
               if preset.get("target_audience") in dictionaries["target_audiences"] else 0),
    )
    lifecycle_stage = st.selectbox("Этап жизненного пути", ["— не выбрано —"] + dictionaries.get("lifecycle_stages", LIFECYCLE_STAGES))
    max_results = st.slider("Кол-во результатов", 1, 50, preset.get("max_results", 10))

    metadata = {
        "suggested_direction": direction if direction != _NONE else None,
        "suggested_category": category if category != _NONE else None,
        "suggested_target_audience": target_audience if target_audience != _NONE else None,
        "lifecycle_stage": lifecycle_stage if lifecycle_stage != _NONE else None,
    }

    col1, col2 = st.columns(2)
    if col1.button("Запустить поиск", type="primary", disabled=not query.strip()):
        try:
            result = run_search(query, _build_chain(), max_results=max_results, metadata=metadata)
            st.success(f"Готово: run_id={result['run_id']}, находок={result['result_count']}")
        except QuotaExceeded as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001 — показать пользователю причину сбоя
            st.error(f"Ошибка запуска поиска: {exc}")

    st.divider()
    st.subheader("Сохранить как пресет")
    preset_name = st.text_input("Имя пресета", value=preset.get("name", ""))
    pcol1, pcol2 = st.columns(2)
    if pcol1.button("Сохранить пресет") and preset_name.strip():
        save_preset({
            "name": preset_name.strip(),
            "query": query,
            "direction": direction if direction != _NONE else None,
            "target_audience": target_audience if target_audience != _NONE else None,
            "max_results": max_results,
        })
        st.success("Пресет сохранён")
        st.rerun()
    if chosen != _NONE and pcol2.button("Удалить текущий пресет"):
        delete_preset(chosen)
        st.rerun()

"""Параметры поиска — запуск search_run + пресеты (issue #19 п.2)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, time

import streamlit as st
import yaml

from src.license.checker import _CONFIG_PATH, LicenseStatus, normalize_domain
from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from src.discovery.presets import delete_preset, load_presets, save_preset
from src.discovery.run_search import run_search
from src.metadata.schema import label_of, load_dictionaries
from src.metadata.profile import LIFECYCLE_STAGES
from src.search.base import QuotaExceeded
from src.search.brave import BraveProvider
from src.search.chain import SearchProviderChain
from src.search.firecrawl import FirecrawlProvider
from src.search.tavily import TavilyProvider

_NONE = "— не выбрано —"


@st.cache_data(ttl=60)
def _found_counts() -> Counter:
    try:
        with GarDiscoveryClient(load_settings()) as client:
            items = client.list_discovered_sources()
    except Exception:  # noqa: BLE001 — счётчики необязательны
        return Counter()
    return Counter(normalize_domain(i["domain"]) for i in items
                   if i.get("domain") and i.get("status") != "rejected")


def _known_domains() -> dict[str, int]:
    """Домены вкладки «Источники» (licenses.yaml ∪ discovered_sources без rejected),
    кроме status=deny -> число находок."""
    registry = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) if _CONFIG_PATH.exists() else {}
    registry = registry or {}
    counts = _found_counts()
    domains = {d: counts.get(d, 0) for d in set(registry) | set(counts)
               if (registry.get(d) or {}).get("status") != LicenseStatus.DENY.value}
    return dict(sorted(domains.items(), key=lambda kv: (-kv[1], kv[0])))


def _build_chain() -> SearchProviderChain:
    # Firecrawl первым звеном (ADR-011, доп. 2026-09-17): Tavily заблокирован
    # сетью, Brave требует карту — оба остаются фолбэком.
    return SearchProviderChain([FirecrawlProvider(), BraveProvider(), TavilyProvider()])


def _date_range() -> tuple[datetime | None, datetime | None]:
    """Необязательный период дат. «До» по умолчанию — сейчас; любую границу можно очистить."""
    now = datetime.now()
    st.session_state.setdefault("sr_to_date", now.date())
    st.session_state.setdefault("sr_to_time", now.time().replace(second=0, microsecond=0))
    st.caption("Период дат (необязательно). Достаточно одной границы; очистите поле даты, чтобы убрать её.")
    c1, c2, c3, c4 = st.columns(4)
    d_from = c1.date_input("От (дата)", value=None, key="sr_from_date")
    t_from = c2.time_input("От (время)", value=time(0, 0), key="sr_from_time")
    d_to = c3.date_input("До (дата)", key="sr_to_date")
    t_to = c4.time_input("До (время)", key="sr_to_time")
    dt_from = datetime.combine(d_from, t_from) if d_from else None
    dt_to = datetime.combine(d_to, t_to) if d_to else None
    if dt_from and dt_to and dt_from > dt_to:
        st.warning("Дата «От» позже даты «До» — результатов не будет.")
    return dt_from, dt_to


def render() -> None:
    st.header("Параметры поиска")
    dictionaries = load_dictionaries()
    presets = load_presets()
    preset_names = [_NONE] + [p["name"] for p in presets]

    chosen = st.selectbox("Пресет", preset_names, key="preset_select")
    preset = next((p for p in presets if p["name"] == chosen), {}) if chosen != _NONE else {}

    query = st.text_input("Тема поиска", value=preset.get("query", ""))

    def fmt(field):  # русские labels из GAR (ADR-013); _NONE и неизвестные значения — как есть
        return lambda v: label_of(dictionaries, field, v)

    direction = st.selectbox(
        "Направление", [_NONE] + list(dictionaries["directions"].keys()),
        index=(list(dictionaries["directions"].keys()).index(preset["direction"]) + 1
               if preset.get("direction") in dictionaries["directions"] else 0),
        format_func=fmt("direction"),
    )
    categories = dictionaries["directions"].get(direction, []) if direction != _NONE else []
    category = st.selectbox("Категория", [_NONE] + categories, format_func=fmt("category"))
    target_audience = st.selectbox(
        "Целевая аудитория", [_NONE] + dictionaries["target_audiences"],
        index=(dictionaries["target_audiences"].index(preset["target_audience"]) + 1
               if preset.get("target_audience") in dictionaries["target_audiences"] else 0),
        format_func=fmt("target_audience"),
    )
    lifecycle_stage = st.selectbox(
        "Этап жизненного пути", ["— не выбрано —"] + dictionaries.get("lifecycle_stages", LIFECYCLE_STAGES),
        format_func=fmt("lifecycle_stage"))
    known = _known_domains()
    domains_selected = st.multiselect(
        "Домены из источников", list(known),
        default=[d for d in preset.get("domains_selected", []) if d in known],
        format_func=lambda d: f"{d} ({known[d]})",
        placeholder="Выберите или начните вводить домен",
        help="Домены со вкладки «Источники», кроме запрещённых (в скобках — число находок).",
    )
    domains_new = st.text_area(
        "Новые домены (необязательно)", value=preset.get("domains", ""), height=80,
        placeholder="downsyndrome.ru, example.org — через запятую или с новой строки",
        help="Домены, которых ещё нет в списке. Если домены не заданы — поиск по всему интернету.",
    )
    domains = ", ".join(domains_selected) + ", " + domains_new
    date_from, date_to = _date_range()
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
            result = run_search(query, _build_chain(), max_results=max_results, metadata=metadata, domains=domains,
                                date_from=date_from, date_to=date_to)
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
            "domains": domains_new,
            "domains_selected": domains_selected,
        })
        st.success("Пресет сохранён")
        st.rerun()
    if chosen != _NONE and pcol2.button("Удалить текущий пресет"):
        delete_preset(chosen)
        st.rerun()

"""Результаты поиска — таблица discovered_sources, фильтры, bulk (issue #19 п.3)."""
from __future__ import annotations

from urllib.parse import urlsplit

import pandas as pd
import streamlit as st

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from src.license.checker import check_license

_STATUS_OPTIONS = ["new", "approved", "rejected", "queued", "downloaded"]
_NONE = "— не выбрано —"


def _approve(client: GarDiscoveryClient, source: dict) -> None:
    """approve лениво триггерит license-check (issue #3, issue #19 п.3)."""
    domain = source.get("domain") or urlsplit(source["url"]).netloc
    result = check_license(domain, source["url"])
    client.update_discovered_source(
        source["id"], status="approved", license_status=result.status.value,
    )


def render() -> None:
    st.header("Результаты поиска")
    settings = load_settings()

    col1, col2, col3 = st.columns(3)
    status_filter = col1.selectbox("Статус", [_NONE] + _STATUS_OPTIONS)
    domain_filter = col2.text_input("Домен (подстрока)")
    text_filter = col3.text_input("Полнотекстовый фильтр (title/snippet)")
    show_duplicates = st.checkbox("Показывать дубли", value=False)

    try:
        with GarDiscoveryClient(settings) as client:
            rows = client.list_discovered_sources(
                status=status_filter if status_filter != _NONE else None,
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"gar-core-api недоступен: {exc}")
        return

    if domain_filter:
        rows = [r for r in rows if domain_filter.lower() in (r.get("domain") or "").lower()]
    if text_filter:
        needle = text_filter.lower()
        rows = [
            r for r in rows
            if needle in (r.get("title") or "").lower() or needle in (r.get("snippet") or "").lower()
        ]
    if not show_duplicates:
        rows = [r for r in rows if not r.get("is_duplicate")]

    if not rows:
        st.info("Ничего не найдено по текущим фильтрам")
        return

    df = pd.DataFrame(rows)
    df.insert(0, "select", False)
    display_cols = [c for c in [
        "select", "url", "title", "snippet", "domain", "direction", "category",
        "doc_type", "relevance_score", "license_status", "is_duplicate", "status", "found_at",
    ] if c in df.columns]
    edited = st.data_editor(
        df[display_cols], hide_index=True, width="stretch",
        disabled=[c for c in display_cols if c != "select"], key="results_editor",
    )
    selected_ids = df.loc[edited["select"], "id"].tolist() if "id" in df.columns else []
    st.caption(f"Выбрано: {len(selected_ids)}")

    b1, b2, b3 = st.columns(3)
    settings = load_settings()
    if b1.button("Одобрить выбранные", disabled=not selected_ids):
        with GarDiscoveryClient(settings) as client:
            for row_id in selected_ids:
                source = next(r for r in rows if r["id"] == row_id)
                _approve(client, source)
        st.success(f"Одобрено: {len(selected_ids)}")
        st.rerun()
    if b2.button("Отклонить выбранные", disabled=not selected_ids):
        with GarDiscoveryClient(settings) as client:
            for row_id in selected_ids:
                client.update_discovered_source(row_id, status="rejected")
        st.success(f"Отклонено: {len(selected_ids)}")
        st.rerun()
    if b3.button("В очередь загрузки", disabled=not selected_ids):
        with GarDiscoveryClient(settings) as client:
            for row_id in selected_ids:
                client.update_discovered_source(row_id, status="queued")
        st.success(f"В очереди: {len(selected_ids)}")
        st.rerun()

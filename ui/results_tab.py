"""Результаты поиска — таблица discovered_sources, фильтры, bulk (issue #19 п.3)."""
from __future__ import annotations

from collections import Counter
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

    # Перечень доменов из текущих результатов (по статусу), с числом статей
    for r in rows:
        r["domain"] = r.get("domain") or urlsplit(r.get("url") or "").netloc
    domain_counts = Counter(r["domain"] for r in rows if r["domain"])
    domain_options = [_NONE] + sorted(domain_counts)
    domain_filter = col2.selectbox(
        "Домен", domain_options,
        format_func=lambda d: f"Все ({len(rows)})" if d == _NONE else f"{d} ({domain_counts[d]})",
    )

    if domain_filter != _NONE:
        rows = [r for r in rows if r["domain"] == domain_filter]
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
    # п.4: url скрыт, title — кликабельная ссылка на url
    display_cols = [c for c in [
        "select", "title", "domain", "direction", "category",
        "doc_type", "is_duplicate", "status", "found_at",
    ] if c in df.columns]
    # п.1: русские заголовки столбцов
    column_labels = {
        "select": "Выбор",
        "title": "Название",
        "domain": "Домен",
        "direction": "Направление",
        "category": "Категория",
        "doc_type": "Тип документа",
        "is_duplicate": "Дубль",
        "status": "Статус",
        "found_at": "Найдено",
    }
    df_display = df[display_cols].rename(columns=column_labels)
    edited = st.data_editor(
        df_display, hide_index=True, width="stretch",
        disabled=[c for c in df_display.columns if c != column_labels["select"]], key="results_editor",
        column_config={
            # п.4: title кликабельный, ведёт на url; п.2: found_at — datetime
            column_labels["title"]: st.column_config.LinkColumn(
                column_labels["title"], display_text=df["title"].tolist(),
            ),
            column_labels["found_at"]: st.column_config.DatetimeColumn(
                column_labels["found_at"], format="DD.MM.YYYY HH:mm",
            ),
        },
    )
    # Маппинг обратно на оригинальные имена для извлечения id
    selected_mask = edited[column_labels["select"]]
    selected_ids = df.loc[selected_mask, "id"].tolist() if "id" in df.columns else []
    st.caption(f"Выбрано: {len(selected_ids)}")

    b1, b2, b3, b4 = st.columns(4)
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
    if b4.button("Удалить выбранные", disabled=not selected_ids):
        with GarDiscoveryClient(settings) as client:
            for row_id in selected_ids:
                client.delete_discovered_source(row_id)
        st.success(f"Удалено: {len(selected_ids)}")
        st.rerun()

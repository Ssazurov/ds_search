"""Дашборд — воронка found->approved->downloaded->ingested, разбивка по
направлениям, ошибки (issue #20 п.5). ingested считается по факту
gar_document_id в sidecar .json (issue #117, закрывает ADR-002 п.7)."""
from __future__ import annotations

from collections import Counter

import streamlit as st

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from ui.documents_tab import _scan_raw

_FUNNEL_STATUSES = ["new", "approved", "queued", "downloading", "downloaded", "rejected", "error"]


def render() -> None:
    st.header("Дашборд")
    settings = load_settings()
    try:
        with GarDiscoveryClient(settings) as client:
            rows = client.list_discovered_sources()
    except Exception as exc:  # noqa: BLE001
        st.error(f"gar-core-api недоступен: {exc}")
        return

    status_counts = Counter(r.get("status", "new") for r in rows)
    found = len(rows)
    approved = status_counts.get("approved", 0) + status_counts.get("queued", 0) + \
        status_counts.get("downloading", 0) + status_counts.get("downloaded", 0)
    downloaded = status_counts.get("downloaded", 0)
    raw_docs = _scan_raw()
    ingested = sum(1 for r in raw_docs if r.get("gar_document_id"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Найдено", found)
    c2.metric("Одобрено", approved)
    c3.metric("Скачано", downloaded)
    c4.metric("В GAR", ingested, help="По факту gar_document_id в sidecar .json (issue #117)")

    st.subheader("По направлениям")
    by_direction = Counter(r.get("direction") or "—" for r in rows)
    st.bar_chart(by_direction)

    st.subheader("Ошибки последних запусков")
    errors = [r for r in rows if r.get("status") == "error"]
    if errors:
        st.dataframe(
            [{"url": r["url"], "domain": r.get("domain", ""), "title": r.get("title", "")} for r in errors],
            hide_index=True, width="stretch",
        )
    else:
        st.info("Ошибок нет")

    st.caption(f"Документов на диске (raw): {len(raw_docs)}")

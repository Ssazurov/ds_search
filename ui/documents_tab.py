"""Документы — статус по стадиям сканированием ФС, не отдельной таблицей
(issue #20 п.3, ADR-002 уточнения п.3 и открытый вопрос п.7:
metadata/ingestion пока всегда not_started — нет сигнала от ds_ingestion)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1] / "data"
RAW_ROOT = ROOT / "raw"
CLEAN_ROOT = ROOT / "clean"


def _scan_raw() -> list[dict]:
    rows = []
    if not RAW_ROOT.exists():
        return rows
    for meta_path in RAW_ROOT.glob("*/*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("content_status") != "saved":
            continue
        doc_id = meta_path.stem
        clean_exists = (CLEAN_ROOT / meta_path.parent.name / f"{doc_id}.json").exists() if CLEAN_ROOT.exists() else False
        rows.append({
            "doc_id": doc_id,
            "title": meta.get("title") or "",
            "domain": meta.get("source_domain", ""),
            "direction": meta.get("direction", ""),
            "raw": True,
            "clean": clean_exists,
            "metadata": "not_started",
            "ingested": "not_started",
        })
    return rows


def render() -> None:
    st.header("Документы")
    st.caption("Стадии raw/clean — по наличию файлов на диске. metadata/ingestion "
               "пока не трекаются программно (открытый вопрос ADR-002 п.7, нужен сигнал от ds_ingestion).")
    rows = _scan_raw()
    if not rows:
        st.info("Нет сохранённых документов в data/raw")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Всего: {len(df)}, clean: {int(df['clean'].sum())}")

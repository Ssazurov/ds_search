"""Документы — статус по стадиям сканированием ФС, не отдельной таблицей
(issue #20 п.3, ADR-002 уточнения п.3). Кнопки ingestion в GAR (issue #116,
ADR-006 п.5): одиночная и пакетная загрузка через src/gar_ingest/documents.py."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.gar_ingest.documents import ingest_document

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
            "doc_json_path": meta_path,
            "title": meta.get("title") or "",
            "domain": meta.get("source_domain", ""),
            "direction": meta.get("direction", ""),
            "raw": True,
            "clean": clean_exists,
            "metadata": "not_started",
            "gar_document_id": meta.get("gar_document_id"),
            "ingest_error": meta.get("ingest_error"),
        })
    return rows


def _apply_filters(rows: list[dict]) -> list[dict]:
    directions = sorted({r["direction"] for r in rows if r["direction"]})
    domains = sorted({r["domain"] for r in rows if r["domain"]})
    col1, col2 = st.columns(2)
    direction = col1.selectbox("Направление", ["Все"] + directions, key="doc_filter_direction")
    domain = col2.selectbox("Источник", ["Все"] + domains, key="doc_filter_domain")
    filtered = rows
    if direction != "Все":
        filtered = [r for r in filtered if r["direction"] == direction]
    if domain != "Все":
        filtered = [r for r in filtered if r["domain"] == domain]
    return filtered


def _ingest_one(row: dict) -> None:
    try:
        ingest_document(row["doc_json_path"])
        st.toast(f"Загружено: {row['doc_id']}")
    except Exception as exc:  # noqa: BLE001 — ошибка ingestion, не должна ронять UI
        st.error(f"{row['doc_id']}: {exc}")
    st.rerun()


def _ingest_batch(rows: list[dict]) -> None:
    pending = [r for r in rows if not r["gar_document_id"]]
    if not pending:
        st.info("Все документы по текущему фильтру уже загружены в GAR")
        return
    progress = st.progress(0.0, text=f"0/{len(pending)}")
    errors: list[str] = []
    for i, row in enumerate(pending, start=1):
        try:
            ingest_document(row["doc_json_path"])
        except Exception as exc:  # noqa: BLE001 — не роняем весь батч на одной ошибке
            errors.append(f"{row['doc_id']}: {exc}")
        progress.progress(i / len(pending), text=f"{i}/{len(pending)}")
    for err in errors:
        st.error(err)
    st.success(f"Готово: {len(pending) - len(errors)}/{len(pending)} загружено")
    st.rerun()


def render() -> None:
    st.header("Документы")
    st.caption("Стадии raw/clean — по наличию файлов на диске. Ingestion в GAR — "
               "по факту gar_document_id в sidecar .json (issue #116, ADR-006).")
    rows = _scan_raw()
    if not rows:
        st.info("Нет сохранённых документов в data/raw")
        return

    filtered = _apply_filters(rows)
    not_ingested = [r for r in filtered if not r["gar_document_id"]]
    st.button(
        f"Загрузить все не загруженные ({len(not_ingested)})",
        disabled=not not_ingested,
        on_click=_ingest_batch,
        args=(filtered,),
    )

    df = pd.DataFrame([
        {
            "doc_id": r["doc_id"], "title": r["title"], "domain": r["domain"],
            "direction": r["direction"], "raw": r["raw"], "clean": r["clean"],
            "metadata": r["metadata"],
            "ingested": "done" if r["gar_document_id"] else ("error" if r["ingest_error"] else "not_started"),
        }
        for r in filtered
    ])
    st.dataframe(df, width="stretch", hide_index=True)
    st.caption(f"Всего: {len(df)}, clean: {int(df['clean'].sum())}, в GAR: {int((df['ingested'] == 'done').sum())}")

    st.subheader("Загрузка по одному документу")
    for row in filtered:
        c1, c2, c3 = st.columns([5, 2, 2])
        c1.write(f"**{row['title'] or row['doc_id']}** — {row['direction']}/{row['domain']}")
        if row["gar_document_id"]:
            c2.write("✅ в GAR")
        elif row["ingest_error"]:
            c2.write(f"⚠️ {row['ingest_error']}")
        else:
            c2.write("не загружен")
        c3.button("Загрузить в GAR", key=f"ingest_{row['doc_id']}",
                   disabled=bool(row["gar_document_id"]),
                   on_click=_ingest_one, args=(row,))

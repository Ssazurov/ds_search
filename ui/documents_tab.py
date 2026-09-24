"""Документы — статус по стадиям сканированием ФС, не отдельной таблицей
(issue #20 п.3, ADR-002 уточнения п.3). Кнопки ingestion в GAR (issue #116,
ADR-006 п.5): пакетная загрузка через src/gar_ingest/documents.py.
Вид таблицы — по образцу «Результатов» через ui/table_utils.py (issue #270)."""
from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.crawler.manual_add import add_manual_document
from src.gar_ingest.documents import ingest_document
from src.metadata.schema import label_of, load_dictionaries
from ui.table_utils import COLUMN_LABELS, column_settings, datetime_column, link_column, localize

ROOT = Path(__file__).resolve().parents[1] / "data"
RAW_ROOT = ROOT / "raw"
CLEAN_ROOT = ROOT / "clean"

_ALL = "Все"
_STATUS_ORDER = {"error": 0, "pending": 1, "loaded": 2}  # ошибки сверху
_STATUS_CELL = {"loaded": "✅ загружен", "error": "⚠️ ошибка", "pending": "— не загружен"}
_STATUS_FILTER = {"pending": "Не загружены", "error": "Ошибка", "loaded": "Загружены"}


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
        gar_id, error = meta.get("gar_document_id"), meta.get("ingest_error")
        rows.append({
            "doc_id": doc_id,
            "doc_json_path": meta_path,
            "title": meta.get("title") or doc_id,
            "url": meta.get("source_url") or None,
            "domain": meta.get("source_domain", ""),
            "direction": meta.get("direction", ""),
            "category": meta.get("category", ""),
            "doc_type": meta.get("doc_type", ""),
            "clean": clean_exists,
            "gar_document_id": gar_id,
            "ingest_error": error,
            "status": "loaded" if gar_id else ("error" if error else "pending"),
            "added": datetime.fromtimestamp(meta_path.stat().st_mtime),
        })
    return rows


def _apply_filters(rows: list[dict]) -> list[dict]:
    dictionaries = load_dictionaries()
    directions = sorted({r["direction"] for r in rows if r["direction"]})
    domain_counts = Counter(r["domain"] for r in rows if r["domain"])
    c1, c2, c3, c4 = st.columns(4)
    text = c1.text_input("Поиск (название/домен)", key="doc_filter_text").strip().lower()
    status = c2.selectbox(
        "В GAR", [_ALL, *_STATUS_FILTER], key="doc_filter_status",
        format_func=lambda v: _STATUS_FILTER.get(v, _ALL))
    domain = c3.selectbox(
        "Домен", [_ALL, *sorted(domain_counts)], key="doc_filter_domain",
        format_func=lambda d: f"Все ({len(rows)})" if d == _ALL else f"{d} ({domain_counts[d]})")
    direction = c4.selectbox(
        "Направление", [_ALL, *directions], key="doc_filter_direction",
        format_func=lambda v: v if v == _ALL else label_of(dictionaries, "direction", v))
    filtered = rows
    if text:
        filtered = [r for r in filtered if text in r["title"].lower() or text in r["domain"].lower()]
    if status != _ALL:
        filtered = [r for r in filtered if r["status"] == status]
    if domain != _ALL:
        filtered = [r for r in filtered if r["domain"] == domain]
    if direction != _ALL:
        filtered = [r for r in filtered if r["direction"] == direction]
    return sorted(filtered, key=lambda r: (_STATUS_ORDER[r["status"]], r["title"].lower()))


def _delete_files(row: dict) -> None:
    """Удаляет локальные файлы документа: raw meta + content + clean sidecar.
    GAR не трогаем (вариант "а"): если ingested, запись в GAR остаётся."""
    meta = json.loads(row["doc_json_path"].read_text(encoding="utf-8"))
    content_path = meta.get("content_path")
    if content_path and Path(content_path).exists():
        Path(content_path).unlink()
    clean_path = CLEAN_ROOT / row["doc_json_path"].parent.name / f"{row['doc_id']}.json"
    if clean_path.exists():
        clean_path.unlink()
    row["doc_json_path"].unlink(missing_ok=True)


def _delete_batch(rows: list[dict]) -> None:
    errors: list[str] = []
    for row in rows:
        try:
            _delete_files(row)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{row['doc_id']}: {exc}")
    for err in errors:
        st.error(err)
    st.success(f"Удалено: {len(rows) - len(errors)}/{len(rows)}")
    st.rerun()


def _ingest_batch(rows: list[dict]) -> None:
    pending = [r for r in rows if not r["gar_document_id"]]
    if not pending:
        st.info("Все документы уже загружены в GAR")
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


def _add_by_url() -> None:
    url = st.session_state.get("manual_add_url", "").strip()
    if not url:
        return
    result = asyncio.run(add_manual_document(url))
    status = result["status"]
    if status == "added":
        st.session_state["manual_add_msg"] = (
            "success", f"Документ добавлен: {result['doc_id']} (source: {result['source']})"
        )
    elif status == "duplicate":
        st.session_state["manual_add_msg"] = (
            "warning",
            f"Документ с этим URL уже есть ({result['doc_id']}) — используйте reload "
            "для обновления содержимого, не повторное добавление.",
        )
    elif status == "license_pending":
        st.session_state["manual_add_msg"] = (
            "warning",
            f"Домен не проверен: {result['reason']} — проставьте статус во вкладке "
            "«Источники», затем повторите добавление.",
        )
    elif status == "license_denied":
        st.session_state["manual_add_msg"] = ("error", f"Домен запрещён к скачиванию: {result['reason']}")
    else:
        st.session_state["manual_add_msg"] = ("error", f"Не удалось добавить документ: {result['reason']}")


def render() -> None:
    st.header("Документы")
    st.caption("Стадии raw/clean — по наличию файлов на диске. Ingestion в GAR — "
               "по факту gar_document_id в sidecar .json (issue #116, ADR-006).")

    st.subheader("Добавить документ по URL")
    st.caption("Разовое добавление одного известного материала (ADR-0014, issue #204) — "
               "тот же staged crawl и license gate, что и у reload/автосбора.")
    st.text_input("Ссылка на документ", key="manual_add_url")
    st.button("Добавить документ", key="manual_add_btn", on_click=_add_by_url)
    if "manual_add_msg" in st.session_state:
        level, msg = st.session_state.pop("manual_add_msg")
        getattr(st, level)(msg)

    st.divider()
    rows = _scan_raw()
    if not rows:
        st.info("Нет сохранённых документов в data/raw")
        return

    filtered = _apply_filters(rows)
    if not filtered:
        st.info("Ничего не найдено по текущим фильтрам")
        return

    labels = {
        **COLUMN_LABELS, "clean": "Очищен", "gar": "В GAR", "error": "Ошибка", "added": "Добавлен",
    }
    df = pd.DataFrame([
        {
            "title": r["title"], "url": r["url"], "domain": r["domain"],
            "direction": r["direction"], "category": r["category"], "doc_type": r["doc_type"],
            "clean": r["clean"], "gar": _STATUS_CELL[r["status"]],
            "error": r["ingest_error"] or "", "added": r["added"],
        }
        for r in filtered
    ])
    df.insert(0, "select", False)
    order, config = column_settings(
        "documents", {k: labels[k] for k in ("select", "title", "url", "domain", "direction", "category",
                                             "doc_type", "clean", "gar", "error", "added")},
        {labels["url"]: link_column(), labels["added"]: datetime_column(labels["added"])})
    edited = st.data_editor(
        localize(df).rename(columns=labels), hide_index=True, width="stretch",
        disabled=[c for c in labels.values() if c != labels["select"]], key="doc_table_editor",
        column_order=order, column_config=config,
    )
    selected_rows = [filtered[i] for i in edited.index[edited[labels["select"]]]]
    st.caption(
        f"Всего: {len(df)}, очищено: {int(df['clean'].sum())}, "
        f"в GAR: {sum(r['status'] == 'loaded' for r in filtered)}, выбрано: {len(selected_rows)}"
    )

    not_loaded = [r for r in selected_rows if not r["gar_document_id"]]
    b1, b2 = st.columns(2)
    if b1.button(f"Загрузить в GAR выбранные ({len(not_loaded)})", disabled=not not_loaded,
                 key="ingest_selected_btn"):
        _ingest_batch(not_loaded)
    if b2.button("Удалить выбранные", disabled=not selected_rows, key="delete_selected_btn"):
        _delete_batch(selected_rows)

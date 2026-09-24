"""Общие помощники таблиц вкладок админки (issue #270, #272):
русские заголовки, labels справочников, выбор/порядок/ширина колонок с сохранением."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.metadata.schema import label_of, load_dictionaries

try:  # drag-and-drop список; без пакета — fallback на multiselect
    from streamlit_sortables import sort_items
except ImportError:  # pragma: no cover
    sort_items = None

DICT_FIELDS = ("direction", "category", "doc_type")
PREFS_PATH = Path(__file__).resolve().parents[1] / "config" / "ui_prefs.json"
WIDTHS = ("small", "medium", "large")
_DEFAULT_WIDTH = "по умолчанию"

# Русские заголовки, общие для обеих вкладок
COLUMN_LABELS = {
    "select": "Выбор",
    "title": "Название",
    "url": "Ссылка",
    "domain": "Домен",
    "direction": "Направление",
    "category": "Категория",
    "doc_type": "Тип",
}


def localize(df: pd.DataFrame, fields: tuple[str, ...] = DICT_FIELDS) -> pd.DataFrame:
    """Копия df, где коды справочников заменены русскими labels (ADR-013)."""
    dictionaries = load_dictionaries()
    out = df.copy()
    for field in fields:
        if field in out.columns:
            out[field] = out[field].map(
                lambda v, f=field: label_of(dictionaries, f, v) if isinstance(v, str) and v else v)
    return out


def link_column():
    """Узкая иконка-ссылка (display_text один на всю колонку, per-row не поддерживается)."""
    return st.column_config.LinkColumn("Ссылка", display_text=":material/open_in_new:", width="small")


def datetime_column(label: str):
    return st.column_config.DatetimeColumn(label, format="DD.MM.YYYY HH:mm")


# --- настройки колонок: видимость, порядок, ширина (issue #272) ---

def load_prefs(path: Path = PREFS_PATH) -> dict:
    """Весь файл настроек; отсутствующий/битый файл = пустые настройки."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_prefs(prefs: dict, path: Path = PREFS_PATH) -> None:
    """Атомарная запись (tmp + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(prefs, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _valid_width(w) -> bool:
    return w in WIDTHS


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def merge_settings(saved: dict | None, columns: list[str], pinned: tuple[str, ...] = ()) -> dict:
    """Сохранённые настройки + актуальный набор колонок: новые — в конец,
    удалённые — пропускаются, pinned не скрываются, битые ширины отбрасываются."""
    saved = saved if isinstance(saved, dict) else {}
    saved_order = [c for c in _as_list(saved.get("order")) if c in columns]
    order = list(dict.fromkeys(saved_order)) + [c for c in columns if c not in saved_order]
    hidden = [c for c in _as_list(saved.get("hidden")) if c in columns and c not in pinned]
    widths = saved.get("widths")
    widths = {c: w for c, w in widths.items() if c in columns and _valid_width(w)} if isinstance(widths, dict) else {}
    return {"order": order, "hidden": hidden, "widths": widths}


def column_settings(table_key: str, columns: dict[str, str], base_config: dict | None = None,
                    pinned: tuple[str, ...] = ("select", "title")) -> tuple[list[str], dict]:
    """Popover «Колонки» над таблицей. columns: технический ключ -> имя колонки в df
    (в порядке по умолчанию). Возвращает (column_order, column_config) для st.data_editor;
    в prefs хранятся только технические ключи."""
    ver = st.session_state.get(f"{table_key}__ver", 0)
    kp = f"{table_key}_v{ver}"
    prefs = load_prefs()
    cur = merge_settings(prefs.get(table_key), list(columns), pinned)
    names = {k: columns[k] for k in cur["order"]}
    by_name = {v: k for k, v in columns.items()}

    with st.popover("⚙ Колонки"):
        optional = [names[k] for k in cur["order"] if k not in pinned]
        shown = st.multiselect(
            "Показывать", optional, default=[names[k] for k in cur["order"] if k not in pinned and k not in cur["hidden"]],
            key=f"{kp}_shown")
        st.caption("Порядок колонок — перетащите:")
        ordered = list(names.values())
        if sort_items is not None:
            ordered = sort_items(ordered, key=f"{kp}_sort")
        else:
            st.caption("(streamlit-sortables не установлен — порядок по умолчанию)")
        with st.expander("Ширина"):
            widths = {}
            for k in cur["order"]:
                w = st.selectbox(
                    names[k], [_DEFAULT_WIDTH, *WIDTHS],
                    index=(WIDTHS.index(cur["widths"][k]) + 1) if k in cur["widths"] else 0,
                    key=f"{kp}_w_{k}")
                if w != _DEFAULT_WIDTH:
                    widths[k] = w
        b1, b2 = st.columns(2)
        if b1.button("Сохранить", key=f"{table_key}_cols_save"):
            new_order = [by_name[n] for n in ordered if n in by_name]
            new_hidden = [k for k in new_order if k not in pinned and names[k] not in shown]
            save_prefs({**load_prefs(), table_key: {"order": new_order, "hidden": new_hidden, "widths": widths}})
            st.session_state[f"{table_key}__ver"] = ver + 1
            st.rerun()
        if b2.button("Сбросить", key=f"{table_key}_cols_reset"):
            save_prefs({k: v for k, v in load_prefs().items() if k != table_key})
            st.session_state[f"{table_key}__ver"] = ver + 1
            st.rerun()

    order = [columns[k] for k in cur["order"] if k not in cur["hidden"]]
    config = dict(base_config or {})
    for k, w in cur["widths"].items():
        name = columns[k]
        config[name] = {**(config.get(name) or {}), "width": w}
    return order, config

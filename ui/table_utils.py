"""Общие помощники таблиц вкладок «Результаты» и «Документы» (issue #270)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.metadata.schema import label_of, load_dictionaries

DICT_FIELDS = ("direction", "category", "doc_type")

# Русские заголовки, общие для обеих вкладок
COLUMN_LABELS = {
    "select": "Выбор",
    "title": "Название",
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

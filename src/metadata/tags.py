"""Нормализация тегов (ADR-0015/ADR-0028, ds_search#483).

Зеркало gar-core-api/services/tags.py — независимая копия, т.к. репозитории
не шарят пакет; правила нормализации должны совпадать (клиент и сервер
приводят теги к одному виду), поэтому логику менять синхронно в обоих местах.
"""
from __future__ import annotations

import re

MAX_TAGS = 10
MAX_TAG_LEN = 40


def normalize_tag(value: object) -> str:
    s = re.sub(r"\s+", " ", str(value or "").strip()).lower().replace("ё", "е")
    return s[:MAX_TAG_LEN].strip()


def normalize_tags(values) -> list[str]:
    """trim, lowercase, ё->е, схлопнутые пробелы, без дублей, до 10 тегов по 40 символов.

    Строка — разбивается по запятой (ручной ввод в Streamlit / GAR keywords)."""
    if not values:
        return []
    if isinstance(values, str):
        values = values.split(",")
    out: list[str] = []
    for v in values:
        t = normalize_tag(v)
        if t and t not in out:
            out.append(t)
        if len(out) >= MAX_TAGS:
            break
    return out

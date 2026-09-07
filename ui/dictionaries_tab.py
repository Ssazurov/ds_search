"""Справочники — CRUD напрямую в config/categories.yaml (issue #19 п.1)."""
from __future__ import annotations

import streamlit as st

from src.metadata.schema import load_dictionaries, save_dictionaries

# license_statuses — фиксированный enum backend'а, не редактируется.
_EDITABLE_LIST_KEYS = ["doc_types", "target_audiences", "age_groups"]


def _edit_list(label: str, key: str, items: list[str]) -> list[str]:
    st.subheader(label)
    items = list(items)
    for i, val in enumerate(items):
        cols = st.columns([5, 1])
        items[i] = cols[0].text_input(f"{key}_{i}", value=val, label_visibility="collapsed")
        if cols[1].button("Удалить", key=f"del_{key}_{i}"):
            items.pop(i)
            return items
    new_val = st.text_input(f"Новое значение ({label})", key=f"new_{key}")
    if st.button(f"Добавить в «{label}»", key=f"add_{key}") and new_val.strip():
        items.append(new_val.strip())
    return [v for v in items if v.strip()]


def render() -> None:
    st.header("Справочники")
    st.caption("Источник правды — config/categories.yaml. Изменения сохраняются кнопкой ниже.")
    dictionaries = load_dictionaries()

    st.subheader("Направления и категории (directions)")
    directions = dict(dictionaries["directions"])
    direction_names = list(directions.keys())
    new_direction = st.text_input("Новое направление", key="new_direction")
    if st.button("Добавить направление") and new_direction.strip() and new_direction.strip() not in directions:
        directions[new_direction.strip()] = []
        direction_names.append(new_direction.strip())

    for direction in direction_names:
        with st.expander(direction, expanded=False):
            directions[direction] = _edit_list(f"Категории: {direction}", f"cat_{direction}", directions[direction])
            if st.button(f"Удалить направление «{direction}»", key=f"del_dir_{direction}"):
                directions.pop(direction, None)

    dictionaries["directions"] = directions
    for key, label in [
        ("doc_types", "Типы документов"),
        ("target_audiences", "Целевая аудитория"),
        ("age_groups", "Возрастные группы"),
    ]:
        dictionaries[key] = _edit_list(label, key, dictionaries[key])

    st.divider()
    if st.button("Сохранить справочники", type="primary"):
        save_dictionaries(dictionaries)
        st.success("config/categories.yaml обновлён")
        st.rerun()

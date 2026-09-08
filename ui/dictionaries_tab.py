"""Справочники — CRUD directions/categories с отложенным сохранением."""
from __future__ import annotations

import streamlit as st

from src.metadata.schema import load_dictionaries, save_dictionaries, validate_dictionaries

# license_statuses and the other auxiliary lists are read-only in this UI.


def _draft() -> dict:
    if "dictionaries_draft" not in st.session_state:
        st.session_state.dictionaries_draft = load_dictionaries()
    return st.session_state.dictionaries_draft


def _edit_categories(direction: str, items: list[str]) -> None:
    for index, category in enumerate(list(items)):
        cols = st.columns([4, 1, 1])
        renamed = cols[0].text_input("Категория", value=category, key=f"cat_{direction}_{index}").strip()
        if renamed != category:
            items[index] = renamed
        if cols[1].button("Удалить", key=f"del_cat_{direction}_{index}"):
            st.session_state.pending_delete = ("category", direction, category)
            st.rerun()
    new_category = st.text_input("Новая категория", key=f"new_cat_{direction}")
    if st.button("Добавить категорию", key=f"add_cat_{direction}"):
        value = new_category.strip()
        if value and value not in items:
            items.append(value)
            st.session_state.dictionaries_draft["directions"][direction] = items
            st.rerun()
        else:
            st.error("Категория должна быть уникальным непустым идентификатором")


def render() -> None:
    st.header("Справочники")
    st.caption("Источник правды — config/categories.yaml. Изменения сохраняются кнопкой ниже.")
    dictionaries = _draft()

    st.subheader("Направления и категории (directions)")
    directions = dict(dictionaries["directions"])
    new_direction = st.text_input("Новое направление", key="new_direction")
    if st.button("Добавить направление"):
        value = new_direction.strip()
        if value and value not in directions:
            directions[value] = []
            dictionaries["directions"] = directions
            st.rerun()
        else:
            st.error("Направление должно быть уникальным непустым идентификатором")

    for direction in list(directions):
        with st.expander(direction, expanded=False):
            renamed = st.text_input("Новое имя направления", value=direction, key=f"rename_dir_{direction}").strip()
            if st.button("Переименовать направление", key=f"apply_dir_{direction}"):
                if renamed != direction and renamed and renamed not in directions:
                    directions[renamed] = directions.pop(direction)
                    dictionaries["directions"] = directions
                    st.rerun()
                st.error("Новое имя должно быть уникальным идентификатором")
            _edit_categories(direction, directions[direction])
            if st.button(f"Удалить направление «{direction}»", key=f"del_dir_{direction}"):
                st.session_state.pending_delete = ("direction", direction, len(directions[direction]))
                st.rerun()

    dictionaries["directions"] = directions
    st.info("doc_types, target_audiences, age_groups и license_statuses защищены от изменений в этой вкладке.")

    pending = st.session_state.get("pending_delete")
    if pending:
        kind, direction, detail = pending
        if kind == "direction":
            message = f"Удалить направление «{direction}» и {detail} связанных категорий?"
        else:
            message = f"Удалить категорию «{detail}» из направления «{direction}»?"
        st.warning(message)
        yes, no = st.columns(2)
        if yes.button("Подтвердить удаление", key="confirm_delete"):
            if kind == "direction":
                directions.pop(direction, None)
            else:
                directions[direction].remove(detail)
            dictionaries["directions"] = directions
            del st.session_state.pending_delete
            st.rerun()
        if no.button("Отмена", key="cancel_delete"):
            del st.session_state.pending_delete
            st.rerun()

    st.divider()
    if st.button("Сохранить справочники", type="primary"):
        try:
            validate_dictionaries(dictionaries)
            save_dictionaries(dictionaries)
        except (OSError, ValueError) as exc:
            st.error(f"Справочники не сохранены: {exc}")
        else:
            st.success("config/categories.yaml обновлён")
            del st.session_state.dictionaries_draft
            st.rerun()

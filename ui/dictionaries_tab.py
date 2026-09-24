"""Справочники — read-only просмотр (ADR-013). Источник правды — GAR (sindrom-dauna);
правки делаются только там, здесь — кнопка «Обновить из GAR»."""
from __future__ import annotations

import streamlit as st

from src.metadata.gar_schema import GarSchemaError
from src.metadata.schema import label_of, load_dictionaries
from src.metadata.sync_from_gar import sync_from_gar


def render() -> None:
    st.header("Справочники")
    st.caption(
        "Источник правды — GAR (датасет sindrom-dauna). Направления и категории редактируются "
        "только там; здесь — просмотр. После правок в GAR нажмите «Обновить из GAR»."
    )
    if st.button("Обновить из GAR", type="primary"):
        try:
            sync_from_gar()
        except (GarSchemaError, OSError, ValueError) as exc:
            st.error(f"Не удалось обновить из GAR: {exc}")
        else:
            st.success("Справочники обновлены из GAR")
            st.rerun()

    dictionaries = load_dictionaries()
    st.subheader("Направления и категории")
    for direction, categories in dictionaries["directions"].items():
        with st.expander(f"{label_of(dictionaries, 'direction', direction)} · {len(categories)}"):
            st.caption(f"value: `{direction}`")
            for category in categories:
                st.markdown(f"- {label_of(dictionaries, 'category', category)} (`{category}`)")

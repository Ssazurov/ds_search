"""Новости — ревью LLM-черновиков (issue #48, ADR-003).

Список/сортировка по свежести (created_at DESC — уже в list_news_items),
фильтр по статусу, инлайн-редактирование, удаление, публикация (смена
статуса на published; сама доставка в ds_site/GAR — issue #49, вне scope).
"""
from __future__ import annotations

import streamlit as st

from src.news import db

CHANNEL_OPTIONS = ["telegram"]
STATUS_LABELS = {"draft": "Черновик", "published": "Опубликовано", "rejected": "Отклонено"}


def _render_item(item: dict) -> None:
    title = item["title"] or "(без заголовка)"
    with st.expander(f"[{STATUS_LABELS.get(item['status'], item['status'])}] {title}"):
        st.caption(f"{item['source_url']} · создано {item['created_at']}")
        new_title = st.text_input("Заголовок", item["title"], key=f"title_{item['id']}")
        new_summary = st.text_area("Краткое содержание", item.get("summary") or "", key=f"sum_{item['id']}")
        new_body = st.text_area("Текст (markdown)", item.get("body_md") or "", height=200, key=f"body_{item['id']}")
        new_tags = st.text_input(
            "Теги (через запятую)", ", ".join(item.get("tags") or []), key=f"tags_{item['id']}"
        )
        new_channels = st.multiselect(
            "Каналы публикации", CHANNEL_OPTIONS, default=item.get("channels") or [],
            key=f"ch_{item['id']}",
        )

        cols = st.columns(4)
        if cols[0].button("Сохранить", key=f"save_{item['id']}"):
            db.update_news_item(item["id"], {
                "title": new_title,
                "summary": new_summary,
                "body_md": new_body,
                "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
                "channels": new_channels,
            })
            st.success("Сохранено")
            st.rerun()
        if item["status"] != "published" and cols[1].button("Опубликовать", key=f"pub_{item['id']}"):
            db.update_status(item["id"], "published")
            st.success("Опубликовано")
            st.rerun()
        if item["status"] != "rejected" and cols[2].button("Отклонить", key=f"rej_{item['id']}"):
            db.update_status(item["id"], "rejected")
            st.rerun()
        if cols[3].button("Удалить", key=f"del_{item['id']}"):
            db.delete_news_item(item["id"])
            st.rerun()


def render() -> None:
    st.header("Новости")
    db.init_db()

    status_filter = st.selectbox(
        "Статус", ["все"] + list(STATUS_LABELS.keys()),
        format_func=lambda s: "Все" if s == "все" else STATUS_LABELS[s],
    )
    status = None if status_filter == "все" else status_filter

    items = db.list_news_items(status=status)  # уже ORDER BY created_at DESC
    if not items:
        st.info("Нет новостей по выбранному фильтру")
        return

    st.caption(f"Всего: {len(items)}")
    for item in items:
        _render_item(item)

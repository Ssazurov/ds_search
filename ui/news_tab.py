"""Новости — ревью LLM-черновиков (issue #48, ADR-003).

Список/сортировка по свежести (created_at DESC — уже в list_news_items),
фильтр по статусу, инлайн-редактирование, удаление, публикация (смена
статуса на published + ingestion в GAR doc_type=news, issue #49 — ds_site
свой контент не хранит, читает через GAR, отдельного push в сайт не нужно).
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.news import db, publish
from src.news.manual import DEFAULT_SOURCE_NAME, create_manual_draft

CHANNEL_OPTIONS = ["telegram"]
STATUS_LABELS = {"draft": "Черновик", "published": "Опубликовано", "rejected": "Отклонено"}


def _render_item(item: dict) -> None:
    title = item["title"] or "(без заголовка)"
    with st.expander(f"[{STATUS_LABELS.get(item['status'], item['status'])}] {title}"):
        st.caption(f"{item['source_url']} · создано {item['created_at']}")
        new_title = st.text_input("Заголовок", item["title"], key=f"title_{item['id']}")
        new_source = st.text_input("Источник", item.get("source_name") or "", key=f"src_{item['id']}")
        new_summary = st.text_area("Краткое содержание", item.get("summary") or "", key=f"sum_{item['id']}")
        new_body = st.text_area("Текст (markdown)", item.get("body_md") or "", height=200, key=f"body_{item['id']}")
        new_tags = st.text_input(
            "Теги (через запятую)", ", ".join(item.get("tags") or []), key=f"tags_{item['id']}"
        )
        new_channels = st.multiselect(
            "Каналы публикации", CHANNEL_OPTIONS, default=item.get("channels") or [],
            key=f"ch_{item['id']}",
        )

        # issue #198: редактируемая дата публикации — источник даты
        # выбирается тумблером, "Вручную" открывает date/time-инпуты.
        source_dt_raw = item.get("source_published_at")
        pub_options = ["Сейчас"] + (["Дата источника"] if source_dt_raw else []) + ["Вручную"]
        pub_mode = st.radio(
            "Дата публикации", pub_options, horizontal=True, key=f"pubmode_{item['id']}",
        )
        if pub_mode == "Сейчас":
            new_published_at = datetime.now().isoformat(sep=" ", timespec="seconds")
        elif pub_mode == "Дата источника":
            new_published_at = source_dt_raw
        else:
            raw_pub = item.get("published_at") or source_dt_raw
            try:
                default_dt = datetime.fromisoformat(raw_pub) if raw_pub else datetime.now()
            except ValueError:
                default_dt = datetime.now()
            d = st.date_input("Дата", default_dt.date(), key=f"pubdate_{item['id']}")
            t = st.time_input("Время", default_dt.time(), key=f"pubtime_{item['id']}")
            new_published_at = datetime.combine(d, t).isoformat(sep=" ", timespec="seconds")
        st.caption(f"Будет сохранено как дата публикации: {new_published_at}")

        cols = st.columns(4)
        if cols[0].button("Сохранить", key=f"save_{item['id']}"):
            db.update_news_item(item["id"], {
                "title": new_title,
                "source_name": new_source.strip() or None,
                "summary": new_summary,
                "body_md": new_body,
                "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
                "channels": new_channels,
                "published_at": new_published_at,
            })
            st.success("Сохранено")
            st.rerun()
        if item["status"] != "published" and cols[1].button("Опубликовать", key=f"pub_{item['id']}"):
            # issue: status не должен фиксироваться как published, если
            # ingestion в GAR провалился (publish_news_item требует
            # status="published" до вызова — поэтому ставим временно и
            # откатываем в draft при ошибке, чтобы не терять item молча
            # в "опубликовано", хотя в GAR его нет).
            db.update_status(item["id"], "published")
            try:
                publish.publish_news_item(item["id"])
                st.success("Опубликовано и загружено в GAR")
            except publish.GarPublishError as exc:
                db.update_status(item["id"], "draft")
                st.warning(f"Публикация не удалась, статус возвращён в черновик: {exc}")
            st.rerun()
        if item.get("gar_document_id") and cols[1].button("Переотправить в GAR", key=f"repub_{item['id']}"):
            try:
                publish.publish_news_item(item["id"], force=True)
                st.success("Переотправлено в GAR")
            except publish.GarPublishError as exc:
                st.warning(f"Ingestion в GAR не удался: {exc}")
            st.rerun()
        elif item["status"] == "published" and item.get("publish_error"):
            st.error(f"GAR ingestion не удался: {item['publish_error']}")
        if item["status"] != "rejected" and cols[2].button("Отклонить", key=f"rej_{item['id']}"):
            db.update_status(item["id"], "rejected")
            st.rerun()
        if cols[3].button("Удалить", key=f"del_{item['id']}"):
            if item.get("gar_document_id"):
                try:
                    publish.revoke_news_item(item["id"])
                except publish.GarPublishError as exc:
                    st.error(f"Не удалось отозвать документ из GAR, запись не удалена: {exc}")
                    st.stop()
            db.delete_news_item(item["id"])
            st.rerun()


def _render_manual_form() -> None:
    """Ручное создание черновика (issue #217): без LLM и проверки лицензии."""
    with st.expander("Создать черновик вручную"):
        with st.form("manual_draft", clear_on_submit=True):
            title = st.text_input("Заголовок *")
            body = st.text_area("Текст (markdown) *", height=200)
            summary = st.text_area("Краткое содержание (пусто — первые 300 симв. текста)")
            tags = st.text_input("Теги (через запятую)")
            name = st.text_input("Источник", DEFAULT_SOURCE_NAME)
            url = st.text_input("Ссылка (необязательно)")
            pub = st.text_input("Дата публикации источника (необязательно)")
            reviewed = st.checkbox("Проверено, не требует ревью")
            submitted = st.form_submit_button("Создать черновик")
        if submitted:
            try:
                new_id = create_manual_draft(
                    title, body, summary, name, url, pub,
                    tags=tags.split(","), requires_review=not reviewed,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"Черновик создан (id={new_id}) — виден в списке ниже")


def render() -> None:
    st.header("Новости")
    db.init_db()
    _render_manual_form()

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

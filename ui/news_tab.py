"""Новости — ревью LLM-черновиков (issue #48, ADR-003).

Таблица + пакетные действия (issue #282, по образцу «Документов»/
«Результатов», ui/table_utils.py) — вместо N expander-форм на каждую
запись (не масштабировалось при росте числа новостей). Фильтр по статусу
+ поиск по заголовку/источнику; полная форма редактирования — только для
записи, выбранной в таблице. Публикация — смена статуса на published +
ingestion в GAR doc_type=news (issue #49 — ds_site свой контент не
хранит, читает через GAR, отдельного push в сайт не нужно).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.news import db, publish
from src.news.manual import DEFAULT_SOURCE_NAME, create_manual_draft
from ui import notify
from ui.table_utils import column_settings, link_column

CHANNEL_OPTIONS = ["telegram"]
STATUS_LABELS = {"draft": "Черновик", "published": "Опубликовано", "rejected": "Отклонено"}
_ALL = "Все"
_TABLE_LABELS = {
    "select": "Выбор", "status": "Статус", "title": "Заголовок", "source_name": "Источник",
    "url": "Ссылка", "created_at": "Создано", "published_at": "Публикация", "gar": "В GAR",
}


def _fmt_dt(raw: str | None) -> str:
    """ISO-строка → «04.09.2026 10:26» (без секунд и смещения)."""
    try:
        return datetime.fromisoformat(raw).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return str(raw or "—")


def _render_taxonomy(item: dict) -> tuple[str, str]:
    """Направление/категория (ADR-013): опции и labels из живой схемы GAR,
    как в «Документах». Возвращает ("", "") при недоступной схеме."""
    from src.metadata.gar_schema import (
        load_gar_schema, field_options, option_labels, category_options_for_direction,
    )
    try:
        fields = load_gar_schema()
        directions = field_options(fields, "direction")
        labels = option_labels(fields)
    except Exception as exc:  # noqa: BLE001 — деградируем, форма остаётся рабочей
        st.caption(f"Справочник GAR недоступен: {exc}")
        return item.get("direction") or "", item.get("category") or ""
    dir_labels, cat_labels = labels.get("direction", {}), labels.get("category", {})
    iid = item["id"]
    dkey, ckey = f"dir_{iid}", f"cat_{iid}"
    cur_dir = item.get("direction") or ""
    cur_cat = item.get("category") or ""
    c1, c2 = st.columns(2)
    direction = c1.selectbox(
        "Направление", [""] + directions, key=dkey,
        index=([""] + directions).index(cur_dir) if cur_dir in directions else 0,
        format_func=lambda v: v if not v else dir_labels.get(v, v))
    if not direction:
        c2.caption("Категория — сначала выберите направление")
        return "", ""
    cats = category_options_for_direction(fields, direction)
    if st.session_state.get(ckey) not in (None, "", *cats):
        del st.session_state[ckey]  # смена направления → старая категория невалидна
    category = c2.selectbox(
        "Категория", [""] + cats, key=ckey,
        index=([""] + cats).index(cur_cat) if cur_cat in cats else 0,
        format_func=lambda v: v if not v else cat_labels.get(v, v))
    return direction, category


def _render_item(item: dict) -> None:
    """Полная форма редактирования одной записи (только для выбранной в таблице)."""
    st.subheader(item["title"] or "(без заголовка)")
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
    new_direction, new_category = _render_taxonomy(item)

    # issue #198: редактируемая дата публикации — источник даты
    # выбирается тумблером, "Вручную" открывает date/time-инпуты.
    source_dt_raw = item.get("source_published_at")
    pub_options = ["Сейчас"] + (["Дата источника"] if source_dt_raw else []) + ["Вручную"]
    pub_mode = st.radio(
        "Дата публикации", pub_options, horizontal=True, key=f"pubmode_{item['id']}",
        index=pub_options.index("Дата источника") if source_dt_raw else 0,
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
    st.caption(f"Дата публикации: {_fmt_dt(new_published_at)}")

    cols = st.columns(4)
    if cols[0].button("Сохранить", key=f"save_{item['id']}"):
        db.update_news_item(item["id"], {
            "title": new_title,
            "source_name": new_source.strip() or None,
            "summary": new_summary,
            "body_md": new_body,
            "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
            "channels": new_channels,
            "direction": new_direction or None,
            "category": new_category or None,
            "published_at": new_published_at,
        })
        notify.report("success", "Сохранено")
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
            notify.report("success", "Опубликовано и загружено в GAR")
        except publish.GarPublishError as exc:
            db.update_status(item["id"], "draft")
            notify.report("warning", "Публикация не удалась",
                         details=[f"Статус возвращён в черновик: {exc}"])
        st.rerun()
    if item.get("gar_document_id") and cols[1].button("Переотправить в GAR", key=f"repub_{item['id']}"):
        try:
            publish.publish_news_item(item["id"], force=True)
            notify.report("success", "Переотправлено в GAR")
        except publish.GarPublishError as exc:
            notify.report("warning", "Ingestion в GAR не удался", details=[str(exc)])
        st.rerun()
    elif item["status"] == "published" and item.get("publish_error"):
        notify.report("error", "GAR ingestion не удался", details=[item['publish_error']])
    if item["status"] != "rejected" and cols[2].button("Отклонить", key=f"rej_{item['id']}"):
        err = _reject_item(item)
        if err:
            notify.report("error", "Не удалось отозвать документ из GAR",
                          details=["Статус не изменён", err])
        st.rerun()
    if cols[3].button("Удалить", key=f"del_{item['id']}"):
        if item.get("gar_document_id"):
            try:
                publish.revoke_news_item(item["id"])
            except publish.GarPublishError as exc:
                notify.report("error", "Не удалось отозвать документ из GAR",
                             details=["Запись не удалена", str(exc)])
                st.stop()
        db.delete_news_item(item["id"])
        st.rerun()


def _publish_batch(items: list[dict]) -> None:
    ok, errors = 0, []
    for item in items:
        if item["status"] == "published":
            continue
        db.update_status(item["id"], "published")
        try:
            publish.publish_news_item(item["id"])
            ok += 1
        except publish.GarPublishError as exc:
            db.update_status(item["id"], "draft")
            errors.append(f"{item['title']}: {exc}")
    level = notify.outcome_level(ok, len(items))
    notify.report(level, "Опубликовано", stats={"успешно": ok, "всего": len(items)}, details=errors)
    st.rerun()


def _reject_item(item: dict) -> str | None:
    """Отклонить новость. Если она в GAR — сначала отозвать документ; при
    ошибке отзыва статус не меняется. Возвращает текст ошибки или None."""
    if item.get("gar_document_id"):
        try:
            publish.revoke_news_item(item["id"])
        except publish.GarPublishError as exc:
            return f"{item['title']}: {exc}"
    db.update_status(item["id"], "rejected")
    return None


def _reject_batch(items: list[dict]) -> None:
    errors = [e for e in (_reject_item(i) for i in items) if e]
    level = notify.outcome_level(len(items) - len(errors), len(items))
    notify.report(level, "Отклонено", stats={"успешно": len(items) - len(errors), "всего": len(items)},
                  details=errors)
    st.rerun()


def _delete_batch(items: list[dict]) -> None:
    errors = []
    for item in items:
        if item.get("gar_document_id"):
            try:
                publish.revoke_news_item(item["id"])
            except publish.GarPublishError as exc:
                errors.append(f"{item['title']}: {exc}")
                continue
        db.delete_news_item(item["id"])
    ok = len(items) - len(errors)
    level = notify.outcome_level(ok, len(items))
    notify.report(level, "Удалено", stats={"успешно": ok, "всего": len(items)}, details=errors)
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
                notify.report("error", "Ошибка создания черновика", details=[str(exc)])
            else:
                notify.report("success", "Черновик создан", details=[f"id={new_id}"])
                st.rerun()


def render() -> None:
    st.header("Новости")
    db.init_db()
    _render_manual_form()

    c1, c2 = st.columns([1, 2])
    status_filter = c1.selectbox(
        "Статус", [_ALL] + list(STATUS_LABELS.keys()),
        format_func=lambda s: _ALL if s == _ALL else STATUS_LABELS[s],
    )
    search = c2.text_input("Поиск (заголовок/источник)", key="news_search").strip().lower()
    status = None if status_filter == _ALL else status_filter

    items = db.list_news_items(status=status)  # уже ORDER BY created_at DESC
    if search:
        items = [
            i for i in items
            if search in (i["title"] or "").lower() or search in (i.get("source_name") or "").lower()
        ]
    if not items:
        st.info("Нет новостей по выбранному фильтру")
        return

    df = pd.DataFrame([{
        "status": STATUS_LABELS.get(i["status"], i["status"]),
        "title": i["title"] or "(без заголовка)",
        "source_name": i.get("source_name") or "",
        "url": i.get("source_url") or None,
        "created_at": i["created_at"],
        "published_at": i.get("published_at") or "",
        "gar": ("🟥" if i.get("status") == "rejected"
                else "✅" if i.get("gar_document_id") else ("⚠️" if i.get("publish_error") else "")),
    } for i in items])
    df.insert(0, "select", False)

    order, config, sort = column_settings(
        "news", _TABLE_LABELS, {_TABLE_LABELS["url"]: link_column()})
    df_display = df.rename(columns=_TABLE_LABELS)
    if sort:
        df_display = df_display.sort_values(sort[0], ascending=sort[1])
    edited = st.data_editor(
        df_display, hide_index=True, width="stretch",
        disabled=[c for c in _TABLE_LABELS.values() if c != _TABLE_LABELS["select"]],
        key="news_table_editor", column_order=order, column_config=config,
    )
    selected = [items[i] for i in edited.index[edited[_TABLE_LABELS["select"]]]]
    st.caption(f"Всего: {len(items)}, выбрано: {len(selected)}")

    b1, b2, b3 = st.columns(3)
    if b1.button(f"Опубликовать выбранные ({len(selected)})", disabled=not selected, key="news_pub_selected"):
        _publish_batch(selected)
    if b2.button("Отклонить выбранные", disabled=not selected, key="news_rej_selected"):
        _reject_batch(selected)
    if b3.button("Удалить выбранные", disabled=not selected, key="news_del_selected"):
        _delete_batch(selected)

    st.divider()
    if len(selected) == 1:
        _render_item(selected[0])
    elif len(selected) > 1:
        st.info("Выберите одну запись в таблице, чтобы открыть форму редактирования содержимого")
    else:
        st.caption("Выберите запись в таблице, чтобы открыть форму редактирования")

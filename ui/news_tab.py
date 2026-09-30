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

from src.news import db, digest_check, overlap, publish
from src.news.manual import DEFAULT_SOURCE_NAME, create_manual_draft
from ui import notify
from ui.table_utils import column_settings, link_column, action_row

CHANNEL_OPTIONS = ["telegram"]
STATUS_LABELS = {"draft": "Черновик", "published": "Опубликовано", "rejected": "Отклонено"}
FORMAT_LABELS = {"news": "Новость", "digest": "Пересказ"}
_ALL = "Все"
_TABLE_LABELS = {
    "select": "Выбор", "status": "Статус", "format": "Формат", "title": "Заголовок", "source_name": "Источник",
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


_ORIG_BOX = ("max-height:520px;overflow:auto;padding:8px 12px;border:1px solid rgba(128,128,128,.35);"
             "border-radius:6px;font-size:0.9rem;line-height:1.5")


def _render_original(item: dict, draft_body: str) -> None:
    """Левая колонка карточки пересказа: оригинал, фрагменты, совпадающие с
    текущим черновиком (5+ слов подряд, без цитат), подсвечены."""
    st.markdown("**Оригинал** — совпадения с пересказом подсвечены")
    src = item.get("source_text") or ""
    if not src.strip():
        st.warning("Текст оригинала не сохранён — сравнить нельзя")
    else:
        html = overlap.highlight_html(src, overlap.strip_quotes(draft_body))
        st.markdown(f'<div style="{_ORIG_BOX}">{html}</div>', unsafe_allow_html=True)
    st.caption(item.get("source_url") or "")


def _render_digest_report(ev: dict, item: dict, draft_body: str) -> None:
    """Индикатор перекрытия + чеклист + подсветка совпадений в самом пересказе."""
    ov = ev["overlap"]
    m1, m2 = st.columns(2)
    m1.metric("Макс. серия слов", ov["max_run"] if ov else "—",
              help=f"Порог блокировки: {overlap.MAX_RUN_WORDS} слов подряд")
    m2.metric("Перекрытие n-грамм", f"{ov['ratio']:.0%}" if ov else "—",
              help=f"Ориентир: не более {overlap.MAX_RATIO:.0%}")
    if ov and ov["ratio"] > overlap.MAX_RATIO:
        st.warning(f"Перекрытие {ov['ratio']:.0%} выше ориентира {overlap.MAX_RATIO:.0%} (не блокирует)")
    for c in ev["checks"]:
        st.markdown(f"{'✅' if c['ok'] else '❌'} {c['label']}" + (f" — {c['hint']}" if c["hint"] else ""))
    src = item.get("source_text") or ""
    if src.strip():
        with st.expander("Пересказ с подсветкой совпадений"):
            html = overlap.highlight_html(draft_body, src, skip_quotes=True)
            st.markdown(f'<div style="{_ORIG_BOX}">{html}</div>', unsafe_allow_html=True)


def _render_item(item: dict) -> None:
    """Полная форма редактирования одной записи (только для выбранной в таблице).
    Пересказ (format=digest, ds_search#421): слева оригинал с подсветкой
    совпадений, справа редактируемый черновик; чеклист блокирует публикацию."""
    is_digest = item.get("format") == "digest"
    st.subheader(item["title"] or "(без заголовка)")
    st.caption(f"{item['source_url']} · создано {item['created_at']}"
               + (" · формат: пересказ" if is_digest else ""))
    if is_digest:
        left, form = st.columns(2)
    else:
        left, form = None, st.container()
    with form:
        new_title = st.text_input("Заголовок", item["title"], key=f"title_{item['id']}")
        new_source = st.text_input("Источник", item.get("source_name") or "", key=f"src_{item['id']}")
        new_summary = st.text_area("Краткое содержание", item.get("summary") or "", key=f"sum_{item['id']}")
        new_body = st.text_area("Текст (markdown)", item.get("body_md") or "", height=200, key=f"body_{item['id']}")
        new_quotes = ""
        if is_digest:
            new_quotes = st.text_area(
                "Цитаты (по одной в строке; в тексте — в «ёлочках»)",
                "\n".join(item.get("quotes") or []), key=f"quotes_{item['id']}")
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

    payload = {
        "title": new_title,
        "source_name": new_source.strip() or None,
        "summary": new_summary,
        "body_md": new_body,
        "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
        "channels": new_channels,
        "direction": new_direction or None,
        "category": new_category or None,
        "published_at": new_published_at,
    }
    blocked = False
    if is_digest:
        quotes = [q.strip() for q in new_quotes.splitlines() if q.strip()]
        ev = digest_check.evaluate({**item, **payload, "quotes": quotes})
        ov = ev["overlap"] or {}
        payload.update(quotes=quotes, overlap_max_run=ov.get("max_run"), overlap_ratio=ov.get("ratio"))
        blocked = not ev["ok"]
        with left:
            _render_original(item, new_body)
        _render_digest_report(ev, item, new_body)

    cols = action_row(4, "news_item")
    if cols[0].button("Сохранить", key=f"save_{item['id']}"):
        db.update_news_item(item["id"], payload)
        notify.report("success", "Сохранено")
        st.rerun()
    if item["status"] != "published" and cols[1].button(
        "Опубликовать", key=f"pub_{item['id']}", disabled=blocked,
        help="Чеклист пересказа не пройден" if blocked else None,
    ):
        if is_digest:
            db.update_news_item(item["id"], payload)  # публикуем ровно то, что проверено на экране
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
        stop = digest_check.blockers(item)  # пересказ: чеклист (ds_search#421)
        if stop:
            errors.append(f"{item['title']}: чеклист не пройден — {'; '.join(stop)}")
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


def _render_bulk_digest_form() -> None:
    """Массовая переработка ранее загруженных статей корпуса в пересказы
    (issue #422): dry-run считает кандидатов, лимит ограничивает прогон."""
    from src.news.bulk_digest import bulk_digest

    with st.expander("Переработать в пересказы (массово)"):
        st.caption(
            "Статьи корпуса, уже опубликованные в GAR, кроме доменов из "
            "config/digest_bulk.yaml — становятся черновиками-пересказами."
        )
        limit = st.number_input("Лимит за прогон (0 — без лимита)", min_value=0, value=20, key="bulk_digest_limit")
        c1, c2 = st.columns(2)
        if c1.button("Посчитать кандидатов (dry-run)", key="bulk_digest_dry"):
            stats = bulk_digest(dry_run=True)
            notify.report("info", "Кандидатов найдено", stats=stats.as_dict())
            if stats.titles:
                st.write(stats.titles)
        if c2.button("Запустить", key="bulk_digest_run"):
            bar = st.progress(0.0)
            total = bulk_digest(dry_run=True).candidates_total or 1

            def _cb(n: int, title: str) -> None:
                bar.progress(min(n / total, 1.0), text=title)

            stats = bulk_digest(limit=limit or None, progress_cb=_cb)
            notify.report(
                "success" if not stats.errors else "warning",
                "Массовая переработка завершена", stats=stats.as_dict(), details=stats.errors,
            )
            st.rerun()


def _digest_queue() -> list[dict]:
    """Очередь ревью: черновики-пересказы, старые первыми."""
    drafts = [i for i in db.list_news_items(status="draft") if i.get("format") == "digest"]
    return list(reversed(drafts))


def _render_digest_queue() -> None:
    """Пакетный режим (ds_search#421): по одному черновику, «Далее / Опубликовать /
    Отклонить». Опубликованный/отклонённый выпадает из очереди — индекс
    остаётся на следующем."""
    queue = _digest_queue()
    if not queue:
        st.success("Очередь пересказов пуста")
        return
    idx = min(st.session_state.get("digest_q_idx", 0), len(queue) - 1)
    st.caption(f"Пересказ {idx + 1} из {len(queue)}")
    n1, n2, _ = st.columns([1, 1, 4])
    if n1.button("← Назад", disabled=idx == 0, key="digest_q_prev"):
        st.session_state["digest_q_idx"] = idx - 1
        st.rerun()
    if n2.button("Далее →", disabled=idx >= len(queue) - 1, key="digest_q_next"):
        st.session_state["digest_q_idx"] = idx + 1
        st.rerun()
    st.session_state["digest_q_idx"] = idx
    _render_item(queue[idx])


def render() -> None:
    st.header("Новости")
    db.init_db()
    _render_manual_form()
    _render_bulk_digest_form()

    if st.toggle("Пакетный режим: очередь пересказов", key="digest_queue_mode"):
        _render_digest_queue()
        return

    c1, c2, c3 = st.columns([1, 1, 2])
    status_filter = c1.selectbox(
        "Статус", [_ALL] + list(STATUS_LABELS.keys()),
        format_func=lambda s: _ALL if s == _ALL else STATUS_LABELS[s],
    )
    format_filter = c2.selectbox(
        "Формат", [_ALL] + list(FORMAT_LABELS.keys()),
        format_func=lambda f: _ALL if f == _ALL else FORMAT_LABELS[f], key="news_format_filter",
    )
    search = c3.text_input("Поиск (заголовок/источник)", key="news_search").strip().lower()
    status = None if status_filter == _ALL else status_filter

    items = db.list_news_items(status=status)  # уже ORDER BY created_at DESC
    if format_filter != _ALL:
        items = [i for i in items if (i.get("format") or "news") == format_filter]
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
        "format": FORMAT_LABELS.get(i.get("format") or "news", i.get("format")),
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

    b1, b2, b3 = action_row(3, "news")
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

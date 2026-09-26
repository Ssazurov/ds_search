"""Документы — статус по стадиям сканированием ФС, не отдельной таблицей
(issue #20 п.3, ADR-002 уточнения п.3). Кнопки ingestion в GAR (issue #116,
ADR-006 п.5): пакетная загрузка через src/gar_ingest/documents.py.
Вид таблицы — по образцу «Результатов» через ui/table_utils.py (issue #270)."""
from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.crawler.manual_add import add_manual_document
from src.gar_ingest.documents import ingest_document
from src.metadata.schema import label_of, load_dictionaries
from ui.table_utils import COLUMN_LABELS, column_settings, datetime_column, link_column, localize

ROOT = Path(__file__).resolve().parents[1] / "data"
RAW_ROOT = ROOT / "raw"
CLEAN_ROOT = ROOT / "clean"

_ALL = "Все"
_STATUS_ORDER = {"error": 0, "pending": 1, "loaded": 2}  # ошибки сверху
_STATUS_CELL = {"loaded": "✅ загружен", "error": "⚠️ ошибка", "pending": "— не загружен"}
_STATUS_FILTER = {"pending": "Не загружены", "error": "Ошибка", "loaded": "Загружены"}


def _scan_raw() -> list[dict]:
    rows = []
    if not RAW_ROOT.exists():
        return rows
    for meta_path in RAW_ROOT.glob("*/*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("content_status") != "saved":
            continue
        doc_id = meta_path.stem
        clean_exists = (CLEAN_ROOT / meta_path.parent.name / f"{doc_id}.json").exists() if CLEAN_ROOT.exists() else False
        gar_id, error = meta.get("gar_document_id"), meta.get("ingest_error")
        rows.append({
            "doc_id": doc_id,
            "doc_json_path": meta_path,
            "title": meta.get("title") or doc_id,
            "url": meta.get("source_url") or None,
            "domain": meta.get("source_domain", ""),
            "direction": meta.get("direction", ""),
            "category": meta.get("category", ""),
            "doc_type": meta.get("doc_type", ""),
            "content_path": meta.get("content_path"),
            "clean": clean_exists,
            "gar_document_id": gar_id,
            "ingest_error": error,
            "status": "loaded" if gar_id else ("error" if error else "pending"),
            "added": datetime.fromtimestamp(meta_path.stat().st_mtime),
            "local": True,
        })
    return rows


_FILTER_KEYS = ("doc_filter_text", "doc_filter_status", "doc_filter_domain",
                "doc_filter_direction", "doc_filter_local")


def _apply_filters(rows: list[dict]) -> list[dict]:
    dictionaries = load_dictionaries()
    directions = sorted({r["direction"] for r in rows if r["direction"]})
    domain_counts = Counter(r["domain"] for r in rows if r["domain"])
    if st.button("Сбросить", key="doc_filters_reset_btn"):
        for k in _FILTER_KEYS:
            st.session_state.pop(k, None)
        st.rerun()
    c1, c2, c3, c4, c5 = st.columns(5)
    text = c1.text_input("Поиск (название/домен)", key="doc_filter_text").strip().lower()
    status = c2.selectbox(
        "В GAR", [_ALL, *_STATUS_FILTER], key="doc_filter_status",
        format_func=lambda v: _STATUS_FILTER.get(v, _ALL))
    domain = c3.selectbox(
        "Домен", [_ALL, *sorted(domain_counts)], key="doc_filter_domain",
        format_func=lambda d: f"Все ({len(rows)})" if d == _ALL else f"{d} ({domain_counts[d]})")
    direction = c4.selectbox(
        "Направление", [_ALL, *directions], key="doc_filter_direction",
        format_func=lambda v: v if v == _ALL else label_of(dictionaries, "direction", v))
    local = c5.selectbox("Локально", [_ALL, "Да", "Нет"], key="doc_filter_local")
    filtered = rows
    if text:
        filtered = [r for r in filtered if text in r["title"].lower() or text in r["domain"].lower()]
    if status != _ALL:
        filtered = [r for r in filtered if r["status"] == status]
    if domain != _ALL:
        filtered = [r for r in filtered if r["domain"] == domain]
    if direction != _ALL:
        filtered = [r for r in filtered if r["direction"] == direction]
    if local == "Да":
        filtered = [r for r in filtered if r["local"]]
    elif local == "Нет":
        filtered = [r for r in filtered if not r["local"]]
    return sorted(filtered, key=lambda r: (_STATUS_ORDER[r["status"]], r["title"].lower()))


def _fetch_gar_documents() -> dict[str, dict]:
    """Все документы из GAR (issue #295). Вызывается только по кнопке
    «Обновить список GAR», не на каждый рендер вкладки (ADR-014, риск 1) —
    результат кладётся в session_state и живёт до следующего нажатия."""
    from src.gar_ingest.client import GarIngestClient, load_settings
    settings = load_settings()
    with GarIngestClient(settings) as client:
        dataset_id = client.ensure_dataset(settings.dataset_name)
        docs = client.list_documents(dataset_id, status=None)
    return {d["document_id"]: d for d in docs}


def _gar_only_rows(rows: list[dict]) -> list[dict]:
    """Строки для документов из GAR-кэша, у которых нет локального
    raw-файла (issue #295, ADR-014, решение п.1-2). doc_json_path/
    content_path=None -> колонки MD/JSON останутся пустыми (_file_uri)."""
    cache: dict[str, dict] = st.session_state.get("gar_docs_cache") or {}
    local_gar_ids = {r["gar_document_id"] for r in rows if r["gar_document_id"]}
    extra = []
    for doc_id, doc in cache.items():
        if doc_id in local_gar_ids:
            continue
        meta = doc.get("metadata") or {}
        extra.append({
            "doc_id": doc_id,
            "doc_json_path": None,
            "title": meta.get("title") or doc.get("doc_name", doc_id),
            "url": meta.get("source_url") or None,
            "domain": meta.get("source_domain", ""),
            "direction": meta.get("direction", ""),
            "category": meta.get("category", ""),
            "doc_type": doc.get("doc_type", ""),
            "content_path": None,
            "clean": False,
            "gar_document_id": doc_id,
            "ingest_error": None,
            "status": "loaded",
            "added": None,
            "local": False,
        })
    return extra


def _delete_files(row: dict) -> None:
    """Удаляет локальные файлы документа: raw meta + content + clean sidecar.
    GAR не трогаем (вариант "а"): если ingested, запись в GAR остаётся.
    Для строк без локального файла (GAR-only, issue #295) удаление из GAR —
    отдельная задача #299, здесь только пропускаем с явной ошибкой."""
    if row["doc_json_path"] is None:
        raise ValueError("нет локального файла — удаление из GAR см. #299")
    meta = json.loads(row["doc_json_path"].read_text(encoding="utf-8"))
    content_path = meta.get("content_path")
    if content_path and Path(content_path).exists():
        Path(content_path).unlink()
    clean_path = CLEAN_ROOT / row["doc_json_path"].parent.name / f"{row['doc_id']}.json"
    if clean_path.exists():
        clean_path.unlink()
    row["doc_json_path"].unlink(missing_ok=True)


def _delete_batch(rows: list[dict]) -> None:
    errors: list[str] = []
    for row in rows:
        try:
            _delete_files(row)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{row['doc_id']}: {exc}")
    for err in errors:
        st.error(err)
    st.success(f"Удалено: {len(rows) - len(errors)}/{len(rows)}")
    st.rerun()


def _update_document_metadata(doc_json_path: Path, updates: dict) -> None:
    """Обновить метаданные документа в sidecar .json (issue #286)."""
    meta = json.loads(doc_json_path.read_text(encoding="utf-8"))
    meta.update(updates)
    if meta.get("ingest_error") and {"direction", "category", "age"} & updates.keys():
        # правка контролируемых полей — сбрасываем старую ошибку 422, чтобы
        # повторная загрузка не путала пользователя устаревшим текстом
        meta["ingest_error"] = None
    doc_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _patch_gar_metadata(gar_document_id: str, updates: dict) -> None:
    """PATCH метаданных уже загруженного в GAR документа (issue #286).
    Сервер мержит с существующими метаданными (ADR-006)."""
    from src.gar_ingest.client import GarIngestClient, load_settings
    settings = load_settings()
    with GarIngestClient(settings) as client:
        client.patch_document_metadata(gar_document_id, updates)


def _render_metadata_form(selected_rows: list[dict]) -> None:
    """Форма редактирования direction/category/age/needs_review
    перед публикацией (issue #286). publish_permission наследуется от домена
    автоматически при скачивании и здесь не редактируется. Значения
    direction/category берутся из ЖИВОЙ схемы GAR (ADR-013) — только активные
    controlled-опции, чтобы не повторить 422 "unknown value" из-за устаревших
    локальных констант. Для уже загруженных в GAR документов правки уходят
    и в sidecar .json, и через PATCH в сам GAR."""
    if not selected_rows:
        return

    st.subheader("Редактирование метаданных перед публикацией")
    st.caption("publish_permission наследуется от домена автоматически при скачивании и здесь не меняется. "
               "Пустое значение поля = не менять.")

    from src.metadata.schema import AGE_OPTIONS
    from src.metadata.gar_schema import (
        load_gar_schema, field_options, option_labels, category_options_for_direction,
    )

    gar_fields, directions, dir_labels = None, [], {}
    try:
        gar_fields = load_gar_schema()
        directions = field_options(gar_fields, "direction")
        dir_labels = option_labels(gar_fields).get("direction", {})
    except Exception as exc:  # noqa: BLE001 — деградируем, а не роняем вкладку
        st.warning(f"Справочник направлений GAR недоступен ({exc}) — direction/category временно не редактируются.")

    loaded_count = sum(1 for r in selected_rows if r["gar_document_id"])
    st.caption(f"Выбрано: {len(selected_rows)}, из них уже в GAR: {loaded_count} (для них уйдёт PATCH в GAR)")

    # автоподстановка direction/category при смене состава выбора: общее
    # значение — если оно одно на всех выбранных и валидно в живой схеме GAR,
    # иначе пусто ("не выбрано"), чтобы не перезаписать разные документы одним
    # значением по ошибке
    sel_key = tuple(sorted(r["doc_id"] for r in selected_rows))
    if st.session_state.get("_batch_meta_sel_key") != sel_key:
        dirs = {r["direction"] for r in selected_rows}
        common_dir = next(iter(dirs)) if len(dirs) == 1 else ""
        st.session_state["batch_direction"] = common_dir if common_dir in directions else ""
        cats = {r["category"] for r in selected_rows}
        common_cat = next(iter(cats)) if len(cats) == 1 else ""
        valid_cats = category_options_for_direction(gar_fields, common_dir) if common_dir and gar_fields else []
        st.session_state["batch_category"] = common_cat if common_cat in valid_cats else ""
        st.session_state["_batch_meta_sel_key"] = sel_key

    with st.form("batch_metadata_form"):
        st.write("**Пакетное обновление выбранных документов**")
        direction = ""
        category = ""
        if directions:
            direction = st.selectbox(
                "Направление", [""] + directions, key="batch_direction",
                format_func=lambda v: v if not v else dir_labels.get(v, v))
            if direction:
                categories = category_options_for_direction(gar_fields, direction)
                cat_labels = option_labels(gar_fields).get("category", {})
                category = st.selectbox(
                    "Категория", [""] + categories, key="batch_category",
                    format_func=lambda v: v if not v else cat_labels.get(v, v))
            else:
                st.caption("Категория — сначала выберите направление")
        age = st.selectbox("Age (возраст)", [""] + AGE_OPTIONS, key="batch_age")
        needs_review_choice = st.selectbox(
            "Needs review (требует проверки)", ["не менять", "да", "нет"], key="batch_needs_review")

        if st.form_submit_button("Применить ко всем выбранным"):
            updates = {}
            if direction:
                updates["direction"] = direction
            if category:
                updates["category"] = category
            if age:
                updates["age"] = age
            if needs_review_choice != "не менять":
                updates["needs_review"] = needs_review_choice == "да"

            if not updates:
                st.warning("Ничего не выбрано для изменения")
            else:
                errors = []
                for row in selected_rows:
                    try:
                        if row["doc_json_path"] is not None:
                            _update_document_metadata(row["doc_json_path"], updates)
                        if row["gar_document_id"]:
                            _patch_gar_metadata(row["gar_document_id"], updates)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{row['doc_id']}: {exc}")

                for err in errors:
                    st.error(err)
                st.success(f"Обновлено: {len(selected_rows) - len(errors)}/{len(selected_rows)}")
                st.rerun()


def _ingest_batch(rows: list[dict]) -> None:
    pending = [r for r in rows if not r["gar_document_id"]]
    if not pending:
        st.info("Все документы уже загружены в GAR")
        return
    progress = st.progress(0.0, text=f"0/{len(pending)}")
    errors: list[str] = []
    for i, row in enumerate(pending, start=1):
        try:
            ingest_document(row["doc_json_path"])
        except Exception as exc:  # noqa: BLE001 — не роняем весь батч на одной ошибке
            errors.append(f"{row['doc_id']}: {exc}")
        progress.progress(i / len(pending), text=f"{i}/{len(pending)}")
    for err in errors:
        st.error(err)
    st.success(f"Готово: {len(pending) - len(errors)}/{len(pending)} загружено")
    st.rerun()


def _add_by_url() -> None:
    url = st.session_state.get("manual_add_url", "").strip()
    if not url:
        return
    result = asyncio.run(add_manual_document(url))
    status = result["status"]
    if status == "added":
        st.session_state["manual_add_msg"] = (
            "success", f"Документ добавлен: {result['doc_id']} (source: {result['source']})"
        )
    elif status == "duplicate":
        st.session_state["manual_add_msg"] = (
            "warning",
            f"Документ с этим URL уже есть ({result['doc_id']}) — используйте reload "
            "для обновления содержимого, не повторное добавление.",
        )
    elif status == "license_pending":
        st.session_state["manual_add_msg"] = (
            "warning",
            f"Домен не проверен: {result['reason']} — проставьте статус во вкладке "
            "«Источники», затем повторите добавление.",
        )
    elif status == "license_denied":
        st.session_state["manual_add_msg"] = ("error", f"Домен запрещён к скачиванию: {result['reason']}")
    else:
        st.session_state["manual_add_msg"] = ("error", f"Не удалось добавить документ: {result['reason']}")


def render() -> None:
    st.header("Документы")
    st.caption("Стадии raw/clean — по наличию файлов на диске. Ingestion в GAR — "
               "по факту gar_document_id в sidecar .json (issue #116, ADR-006).")

    st.subheader("Добавить документ по URL")
    st.caption("Разовое добавление одного известного материала (ADR-0014, issue #204) — "
               "тот же staged crawl и license gate, что и у reload/автосбора.")
    st.text_input("Ссылка на документ", key="manual_add_url")
    st.button("Добавить документ", key="manual_add_btn", on_click=_add_by_url)
    if "manual_add_msg" in st.session_state:
        level, msg = st.session_state.pop("manual_add_msg")
        getattr(st, level)(msg)

    st.divider()
    c_btn, c_info = st.columns([1, 3])
    if c_btn.button("Обновить список GAR", key="gar_docs_refresh_btn"):
        try:
            st.session_state["gar_docs_cache"] = _fetch_gar_documents()
        except Exception as exc:  # noqa: BLE001 — сеть/GAR недоступны, не роняем вкладку
            st.error(f"Не удалось получить список из GAR: {exc}")
        else:
            st.rerun()
    if "gar_docs_cache" in st.session_state:
        c_info.caption(
            f"GAR-документов в кэше: {len(st.session_state['gar_docs_cache'])} "
            "(обновляется по кнопке, issue #295)"
        )
    else:
        c_info.caption("Список GAR ещё не загружен — нажмите «Обновить список GAR», "
                        "чтобы увидеть документы без локального файла")

    rows = _scan_raw()
    rows = rows + _gar_only_rows(rows)
    if not rows:
        st.info("Нет сохранённых документов в data/raw")
        return

    filtered = _apply_filters(rows)
    if not filtered:
        st.info("Ничего не найдено по текущим фильтрам")
        return

    labels = {
        **COLUMN_LABELS, "clean": "Очищен", "gar": "В GAR", "error": "Ошибка", "added": "Добавлен",
        "md": "MD", "json": "JSON",
    }

    def _file_uri(p) -> str | None:
        # issue #292: ссылка на локальный файл черновика, открывается ОС в
        # приложении по умолчанию для .md/.json (не рендерится в браузере).
        return Path(p).resolve().as_uri() if p else None

    df = pd.DataFrame([
        {
            "title": r["title"], "url": r["url"], "domain": r["domain"],
            "direction": r["direction"], "category": r["category"], "doc_type": r["doc_type"],
            "clean": r["clean"], "gar": _STATUS_CELL[r["status"]],
            "error": r["ingest_error"] or "", "added": r["added"],
            "md": _file_uri(r["content_path"]), "json": _file_uri(r["doc_json_path"]),
        }
        for r in filtered
    ])
    df.insert(0, "select", False)
    order, config, sort = column_settings(
        "documents", {k: labels[k] for k in ("select", "title", "url", "domain", "direction", "category",
                                             "doc_type", "clean", "gar", "error", "added", "md", "json")},
        {labels["url"]: link_column(), labels["added"]: datetime_column(labels["added"]),
         labels["md"]: st.column_config.LinkColumn(
             labels["md"], display_text=":material/description:", width="small"),
         labels["json"]: st.column_config.LinkColumn(
             labels["json"], display_text=":material/data_object:", width="small")})
    df_display = localize(df).rename(columns=labels)
    if sort:
        df_display = df_display.sort_values(sort[0], ascending=sort[1])
    edited = st.data_editor(
        df_display, hide_index=True, width="stretch",
        disabled=[c for c in labels.values() if c != labels["select"]], key="doc_table_editor",
        column_order=order, column_config=config,
    )
    selected_rows = [filtered[i] for i in edited.index[edited[labels["select"]]]]
    st.caption(
        f"Всего: {len(df)}, очищено: {int(df['clean'].sum())}, "
        f"в GAR: {sum(r['status'] == 'loaded' for r in filtered)}, выбрано: {len(selected_rows)}"
    )

    # issue #286: форма редактирования метаданных перед публикацией
    if selected_rows:
        st.divider()
        _render_metadata_form(selected_rows)
        st.divider()

    not_loaded = [r for r in selected_rows if not r["gar_document_id"]]
    b1, b2 = st.columns(2)
    if b1.button(f"Загрузить в GAR выбранные ({len(not_loaded)})", disabled=not not_loaded,
                 key="ingest_selected_btn"):
        _ingest_batch(not_loaded)
    if b2.button("Удалить выбранные", disabled=not selected_rows, key="delete_selected_btn"):
        _delete_batch(selected_rows)

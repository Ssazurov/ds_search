"""Карточка материала: edit/archive/delete с каскадом в GAR (issue #133,
ADR-0005 п.2). Таблица + пакетные действия (issue #284, по образцу
«Новостей» issue #282, ui/table_utils.py) — вместо N expander-форм на
каждый документ. Поиск по заголовку/id на клиенте (GAR API без
limit/offset/search — см. ADR при необходимости пагинации). Полная форма
редактирования (title/summary/reload/delete) — только для документа,
выбранного в таблице. Архивация/возврат доступны и пакетно (массовое
удаление не делаем — необратимо, оставлено только поштучно)."""
from __future__ import annotations

import os

import httpx
import pandas as pd
import streamlit as st

from src.gar_ingest.client import GarIngestClient, GarPublishError, load_settings
from ui.table_utils import column_settings

_STATUS_OPTIONS = {"Активные": "indexed", "Архив": "archived", "Все": None}
_DS_INGESTION_URL = os.environ.get("DS_INGESTION_URL", "http://127.0.0.1:8200")
_TABLE_LABELS = {
    "select": "Выбор", "title": "Заголовок", "status": "Статус",
    "product": "Продукт", "doc_type": "Тип", "version": "Версия",
}


def _reload_from_source(document_id: str) -> dict:
    """POST /reload_by_gar_id на ds_ingestion (issue ds_search#145 /
    ADR-0007): полная перезагрузка metadata+content из локального источника.
    Auth: X-Ingestion-Key, см. ADR-0008."""
    headers = {}
    api_key = os.environ.get("DS_INGESTION_API_KEY")
    if api_key:
        headers["X-Ingestion-Key"] = api_key
    resp = httpx.post(
        f"{_DS_INGESTION_URL}/reload_by_gar_id",
        json={"gar_document_id": document_id}, headers=headers, timeout=120,
    )
    if resp.status_code != 200:
        raise GarPublishError(f"reload {document_id} failed: {resp.status_code} {resp.text}")
    return resp.json()


@st.cache_resource
def _get_client() -> GarIngestClient:
    return GarIngestClient(load_settings())


def _dataset_id(client: GarIngestClient) -> str:
    settings = load_settings()
    return client.ensure_dataset(settings.dataset_name)


def _archive_batch(client: GarIngestClient, docs: list[dict]) -> None:
    errors = []
    for doc in docs:
        try:
            client.archive_document(doc["document_id"])
        except GarPublishError as exc:
            errors.append(f"{doc['document_id']}: {exc}")
    for err in errors:
        st.error(err)
    st.success(f"Архивировано: {len(docs) - len(errors)}/{len(docs)}")
    st.cache_resource.clear()
    st.rerun()


def _unarchive_batch(client: GarIngestClient, docs: list[dict]) -> None:
    errors = []
    for doc in docs:
        try:
            client.unarchive_document(doc["document_id"])
        except GarPublishError as exc:
            errors.append(f"{doc['document_id']}: {exc}")
    for err in errors:
        st.error(err)
    st.success(f"Возвращено: {len(docs) - len(errors)}/{len(docs)}")
    st.cache_resource.clear()
    st.rerun()


def _render_card(client: GarIngestClient, doc: dict) -> None:
    doc_id = doc["document_id"]
    meta = doc.get("metadata") or {}
    title = meta.get("title") or doc.get("doc_name", doc_id)
    st.subheader(title)
    st.caption(f"id={doc_id} · product={doc.get('product')} · "
                f"doc_type={doc.get('doc_type')} · version={doc.get('version')} · "
                f"status={doc.get('status')}")
    new_title = st.text_input("Заголовок", value=meta.get("title", ""), key=f"title_{doc_id}")
    new_summary = st.text_area("Summary", value=meta.get("summary", ""), key=f"sum_{doc_id}")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("💾 Сохранить", key=f"save_{doc_id}"):
        try:
            client.patch_document_metadata(doc_id, {"title": new_title, "summary": new_summary})
            st.success("Сохранено")
            st.cache_resource.clear()
            st.rerun()
        except GarPublishError as exc:
            st.error(str(exc))
    if doc.get("status") == "archived":
        if c2.button("♻️ Вернуть", key=f"unarch_{doc_id}"):
            try:
                client.unarchive_document(doc_id)
                st.cache_resource.clear()
                st.rerun()
            except GarPublishError as exc:
                st.error(str(exc))
    else:
        if c2.button("🗄️ Архивировать", key=f"arch_{doc_id}"):
            try:
                client.archive_document(doc_id)
                st.cache_resource.clear()
                st.rerun()
            except GarPublishError as exc:
                st.error(str(exc))
    if c4.button("🔄 Перезагрузить из источника", key=f"reload_{doc_id}"):
        try:
            report = _reload_from_source(doc_id)
            st.success(
                f"Перезагружено. changed={report['changed_fields']} "
                f"preserved={report['preserved_fields']} "
                f"content_replaced={report['content_replaced']}"
            )
            st.cache_resource.clear()
        except GarPublishError as exc:
            st.error(str(exc))
    confirm_key = f"del_confirm_{doc_id}"
    if st.session_state.get(confirm_key):
        st.warning("Удалить безвозвратно? Данные и ассеты будут стёрты.")
        cc1, cc2 = st.columns(2)
        if cc1.button("Да, удалить", key=f"del_yes_{doc_id}"):
            try:
                client.delete_document(doc_id)
                st.session_state[confirm_key] = False
                st.cache_resource.clear()
                st.rerun()
            except GarPublishError as exc:
                st.error(str(exc))
        if cc2.button("Отмена", key=f"del_no_{doc_id}"):
            st.session_state[confirm_key] = False
            st.rerun()
    else:
        if c3.button("🗑️ Удалить совсем", key=f"del_{doc_id}"):
            st.session_state[confirm_key] = True
            st.rerun()


def render() -> None:
    st.subheader("Материалы (GAR)")
    client = _get_client()
    status_label = st.radio("Показать", list(_STATUS_OPTIONS), horizontal=True)
    try:
        dataset_id = _dataset_id(client)
        docs = client.list_documents(dataset_id, status=_STATUS_OPTIONS[status_label])
    except GarPublishError as exc:
        st.error(f"Не удалось получить список документов: {exc}")
        return
    if not docs:
        st.info("Документов не найдено")
        return

    search = st.text_input("Поиск (заголовок/id)", key="materials_search").strip().lower()
    if search:
        docs = [
            d for d in docs
            if search in ((d.get("metadata") or {}).get("title") or "").lower()
            or search in d["document_id"].lower()
        ]
    if not docs:
        st.info("Ничего не найдено по фильтру")
        return

    df = pd.DataFrame([{
        "title": (d.get("metadata") or {}).get("title") or d.get("doc_name", d["document_id"]),
        "status": d.get("status"),
        "product": d.get("product"),
        "doc_type": d.get("doc_type"),
        "version": d.get("version"),
    } for d in docs])
    df.insert(0, "select", False)

    order, config, sort = column_settings("materials", _TABLE_LABELS, {})
    df_display = df.rename(columns=_TABLE_LABELS)
    if sort:
        df_display = df_display.sort_values(sort[0], ascending=sort[1])
    edited = st.data_editor(
        df_display, hide_index=True, width="stretch",
        disabled=[c for c in _TABLE_LABELS.values() if c != _TABLE_LABELS["select"]],
        key="materials_table_editor", column_order=order, column_config=config,
    )
    selected = [docs[i] for i in edited.index[edited[_TABLE_LABELS["select"]]]]
    st.caption(f"Всего: {len(docs)}, выбрано: {len(selected)}")

    b1, b2 = st.columns(2)
    if b1.button(f"Архивировать выбранные ({len(selected)})", disabled=not selected, key="mat_arch_selected"):
        _archive_batch(client, selected)
    if b2.button("Вернуть выбранные", disabled=not selected, key="mat_unarch_selected"):
        _unarchive_batch(client, selected)

    st.divider()
    if len(selected) == 1:
        _render_card(client, selected[0])
    elif len(selected) > 1:
        st.info("Выберите один документ в таблице, чтобы открыть карточку редактирования")
    else:
        st.caption("Выберите документ в таблице, чтобы открыть карточку")

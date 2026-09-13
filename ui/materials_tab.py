"""Карточка материала: edit/archive/delete с каскадом в GAR (issue #133,
ADR-0005 п.2). Список документов датасета из gar-core-api, для каждого —
редактирование metadata (PATCH, сервер мержит), архивация (скрывает из
/public и chat-retrieval, services/retrieval_planner.py и chat_service.py
фильтруют по status=='indexed') и полное удаление (hard delete)."""
from __future__ import annotations

import streamlit as st

from src.gar_ingest.client import GarIngestClient, GarPublishError, load_settings

_STATUS_OPTIONS = {"Активные": "indexed", "Архив": "archived", "Все": None}


@st.cache_resource
def _get_client() -> GarIngestClient:
    return GarIngestClient(load_settings())


def _dataset_id(client: GarIngestClient) -> str:
    settings = load_settings()
    return client.ensure_dataset(settings.dataset_name)


def _render_card(client: GarIngestClient, doc: dict) -> None:
    doc_id = doc["document_id"]
    meta = doc.get("metadata") or {}
    title = meta.get("title") or doc.get("doc_name", doc_id)
    with st.expander(f"{title}  ·  {doc.get('status')}"):
        st.caption(f"id={doc_id} · product={doc.get('product')} · "
                    f"doc_type={doc.get('doc_type')} · version={doc.get('version')}")
        new_title = st.text_input("Заголовок", value=meta.get("title", ""), key=f"title_{doc_id}")
        new_summary = st.text_area("Summary", value=meta.get("summary", ""), key=f"sum_{doc_id}")
        c1, c2, c3 = st.columns(3)
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
                    st.rerun()
                except GarPublishError as exc:
                    st.error(str(exc))
        else:
            if c2.button("🗄️ Архивировать", key=f"arch_{doc_id}"):
                try:
                    client.archive_document(doc_id)
                    st.rerun()
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
    for doc in docs:
        _render_card(client, doc)

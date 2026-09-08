"""Загрузка — очередь одобренных + ручная (issue #20 п.1-2, ADR-002 уточнения).

Полное скачивание — src/discovery/download.py (не SourceCrawler.run(), см. ADR).
Ручная ссылка идёт "стандартным пайпом" — создаётся как approved находка
(license-check выполнится при скачивании в download_single), ручной файл
сохраняется напрямую с обязательными метаданными (URL/скачивание не нужны).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st

from src.discovery.config import load_settings
from src.discovery.download import DownloadError, download_single
from src.discovery.gar_client import GarDiscoveryClient
from src.metadata.schema import load_dictionaries

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"


def _render_queue() -> None:
    st.subheader("Очередь загрузки")
    settings = load_settings()
    try:
        with GarDiscoveryClient(settings) as client:
            rows = client.list_discovered_sources(status="queued") + \
                   client.list_discovered_sources(status="error")
    except Exception as exc:  # noqa: BLE001
        st.error(f"gar-core-api недоступен: {exc}")
        return

    if not rows:
        st.info("Очередь пуста (нет queued/error находок)")
        return

    for source in rows:
        cols = st.columns([5, 2, 2, 2])
        cols[0].write(f"**{source.get('title') or source['url']}**\n\n{source['url']}")
        cols[1].write(source.get("domain", ""))
        cols[2].write(source.get("status", ""))
        if cols[3].button("Скачать", key=f"dl_{source['id']}"):
            with GarDiscoveryClient(settings) as client:
                try:
                    client.update_discovered_source(source["id"], status="downloading")
                    asyncio.run(download_single(source))
                    client.update_discovered_source(source["id"], status="downloaded")
                    st.success("Скачано")
                except DownloadError as exc:
                    client.update_discovered_source(source["id"], status="error")
                    st.error(f"Ошибка: {exc}")
            st.rerun()


def _save_manual_file(uploaded_file, title: str, direction: str, doc_type: str) -> None:
    import hashlib
    domain = "manual"
    pseudo_url = f"manual://{uploaded_file.name}"
    doc_id = hashlib.sha256(pseudo_url.encode()).hexdigest()[:16]
    out_dir = DATA_ROOT / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded_file.name).suffix or ".bin"
    content_path = out_dir / f"{doc_id}{suffix}"
    content_path.write_bytes(uploaded_file.getvalue())
    meta = {
        "source_url": pseudo_url,
        "source_domain": domain,
        "title": title,
        "direction": direction,
        "doc_type": doc_type,
        "license": "manual_upload",
        "attribution": None,
        "content_path": str(content_path),
        "content_status": "saved",
    }
    (out_dir / f"{doc_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _add_manual_link(url: str, direction: str) -> None:
    settings = load_settings()
    with GarDiscoveryClient(settings) as client:
        run = client.create_search_run(query=f"manual: {url}", provider="manual")
        client.update_search_run(run["id"], status="done")
        client.upsert_discovered_sources(run["id"], [{
            "url": url, "domain": None, "title": url, "direction": direction,
            "status": "approved",
        }])


def _render_manual() -> None:
    st.subheader("Ручная загрузка")
    dictionaries = load_dictionaries()
    directions = list(dictionaries["directions"].keys())
    mode = st.radio("Способ", ["Файл", "Ссылка"], horizontal=True)

    if mode == "Файл":
        uploaded = st.file_uploader("Файл документа")
        title = st.text_input("Заголовок (обязательно)")
        direction = st.selectbox("Направление", directions) if directions else st.text_input("Направление")
        doc_type = st.selectbox("Тип документа", dictionaries.get("doc_types", []) or [""])
        if st.button("Сохранить файл", disabled=not (uploaded and title.strip())):
            _save_manual_file(uploaded, title.strip(), direction, doc_type)
            st.success("Документ сохранён в data/raw/manual/")
            st.rerun()
    else:
        url = st.text_input("URL страницы/документа")
        direction = st.selectbox("Направление", directions, key="link_dir") if directions else st.text_input("Направление", key="link_dir")
        if st.button("Добавить как одобренную находку", disabled=not url.strip()):
            try:
                _add_manual_link(url.strip(), direction)
                st.success("Добавлено в discovered_sources со статусом approved — переведите в очередь во вкладке «Результаты»")
            except Exception as exc:  # noqa: BLE001
                st.error(f"gar-core-api недоступен: {exc}")


def render() -> None:
    st.header("Загрузка")
    _render_queue()
    st.divider()
    _render_manual()

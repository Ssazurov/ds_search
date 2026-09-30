"""Загрузка — очередь одобренных + ручная: файл или ссылка (issue #20 п.1-2, #67, ADR-002).

Скачивание URL — через add_manual_document (единое ядро #313/#314/#315) с dedup
и catalog-фильтром. Ручной файл сохраняется напрямую с обязательными метаданными
(URL/скачивание не нужны).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from src.metadata.schema import label_of, load_dictionaries
from src.metadata.profile import build_ingestion_metadata
from src.crawler.manual_add import add_manual_document
from ui import notify

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"


def _render_queue() -> None:
    st.subheader("Очередь загрузки статей")
    settings = load_settings()
    try:
        with GarDiscoveryClient(settings) as client:
            rows = client.list_discovered_sources(status="queued") + \
                   client.list_discovered_sources(status="error")
    except Exception as exc:  # noqa: BLE001
        notify.report("error", "gar-core-api недоступен", details=[str(exc)])
        return

    if not rows:
        st.info("Очередь пуста (нет queued/error находок)")
        return

    for source in rows:
        cols = st.columns([5, 2, 2, 2, 2])
        cols[0].write(f"**{source.get('title') or source['url']}**\n\n{source['url']}")
        cols[1].write(source.get("domain", ""))
        cols[2].write(source.get("status", ""))
        if cols[3].button("Скачать", key=f"dl_{source['id']}"):
            with GarDiscoveryClient(settings) as client:
                client.update_discovered_source(source["id"], status="downloading")
                result = asyncio.run(add_manual_document(
                    source["url"],
                    direction=source.get("suggested_direction"),
                    category=source.get("suggested_category") or source.get("category"),
                ))
                title_label = source.get("title") or source["url"]
                if result["status"] == "added":
                    client.update_discovered_source(source["id"], status="downloaded")
                    notify.report(
                        "success", "Скачано",
                        {"заголовок": title_label},
                        [f"Путь: {result['meta']['content_path']}", f"ID: {result['doc_id']}"],
                    )
                elif result["status"] == "duplicate":
                    client.update_discovered_source(source["id"], status="downloaded")
                    notify.report(
                        "warning", "Документ уже есть в базе",
                        {"заголовок": title_label},
                        [f"ID: {result['doc_id']}"],
                    )
                else:
                    client.update_discovered_source(source["id"], status="error")
                    notify.report(
                        "error", "Не удалось скачать",
                        {"заголовок": title_label},
                        [result.get("reason", result["status"])],
                    )
            st.rerun()
        if cols[4].button("Удалить", key=f"del_{source['id']}"):
            with GarDiscoveryClient(settings) as client:
                client.delete_discovered_source(source["id"])
            notify.report("success", "Удалено", {"заголовок": source.get("title") or source["url"]})
            st.rerun()


def _save_manual_file(
    uploaded_file, title: str, direction: str, doc_type: str,
    category: str | None = None,
) -> None:
    import hashlib
    domain = "manual"
    pseudo_url = f"manual://{uploaded_file.name}"
    doc_id = hashlib.sha256(pseudo_url.encode()).hexdigest()[:16]
    out_dir = DATA_ROOT / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded_file.name).suffix or ".bin"
    content_path = out_dir / f"{doc_id}{suffix}"
    content_path.write_bytes(uploaded_file.getvalue())
    meta = build_ingestion_metadata(
        source_url=pseudo_url, source_domain=domain, title=title,
        license="manual_upload", category=category,
        direction=direction, doc_type=doc_type, attribution=None,
        content_path=str(content_path), content_status="saved",
    )
    (out_dir / f"{doc_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_link(dictionaries: dict, directions: list) -> None:
    """Форма URL: скачать сразу (issue #67), минуя очередь и модерацию."""
    st.caption(
        "Прямое скачивание сейчас же (минуя очередь и модерацию), license-check — сразу. "
        "Папка — домен URL в data/raw/<домен>/, имя файла — транслит заголовка."
    )
    url = st.text_input("URL страницы/документа", key="link_url")
    direction = (
        st.selectbox("Направление", directions, key="link_dir",
                     format_func=lambda v: label_of(dictionaries, "direction", v))
        if directions else st.text_input("Направление", key="link_dir")
    )
    category = st.selectbox(
        "Категория", [""] + dictionaries["directions"].get(direction, []), key="link_cat",
        format_func=lambda v: label_of(dictionaries, "category", v) if v else "— авто —",
    ) or None
    if st.button("Скачать сейчас", disabled=not url.strip()):
        result = asyncio.run(add_manual_document(
            url.strip(),
            direction=direction,
            category=category,
        ))
        if result["status"] == "added":
            notify.report(
                "success", "Скачано",
                {"URL": url.strip()},
                [f"Путь: {result['meta']['content_path']}", f"ID: {result['doc_id']}"],
            )
        elif result["status"] == "duplicate":
            notify.report(
                "warning", "Документ уже есть в базе",
                {"URL": url.strip()},
                [f"ID: {result['doc_id']}"],
            )
        elif result["status"] in ("license_pending", "license_denied"):
            notify.report(
                "warning", "Проверка лицензии",
                {"URL": url.strip()},
                [result["reason"]],
            )
        else:
            notify.report(
                "error", "Не удалось скачать",
                {"URL": url.strip()},
                [result.get("reason", result["status"])],
            )


def _render_manual() -> None:
    st.subheader("Ручная загрузка статей")
    dictionaries = load_dictionaries()
    directions = list(dictionaries["directions"].keys())
    mode = st.radio("Способ", ["Файл", "Ссылка"], horizontal=True)

    if mode == "Файл":
        uploaded = st.file_uploader("Файл документа")
        title = st.text_input("Заголовок (обязательно)")
        direction = (
            st.selectbox("Направление", directions, format_func=lambda v: label_of(dictionaries, "direction", v))
            if directions else st.text_input("Направление")
        )
        categories = dictionaries["directions"].get(direction, [])
        category = st.selectbox("Категория", [""] + categories,
                                format_func=lambda v: label_of(dictionaries, "category", v))
        doc_type = st.selectbox(
            "Тип документа", dictionaries.get("doc_types", []) or [""],
            format_func=lambda v: label_of(dictionaries, "doc_type", v))
        if st.button("Загрузить", key="upload_file_btn", disabled=not (uploaded and title.strip())):
            _save_manual_file(uploaded, title.strip(), direction, doc_type, category or None)
            notify.report("success", "Документ сохранён", {"путь": "data/raw/<домен>/"})
            st.rerun()
    else:
        _render_link(dictionaries, directions)


def _render_add_news() -> None:
    from ui.news_add import format_selector

    st.subheader("Загрузка новости")
    st.caption("Штатная загрузка одной новости по URL (issue #183) — та же "
               "проверка лицензии домена и LLM-классификация, что и автосбор.")
    news_url = st.text_input("Ссылка на новость", key="add_news_url")
    dictionaries = load_dictionaries()
    auto = "— авто —"
    direction = st.selectbox(
        "Направление", [""] + list(dictionaries["directions"].keys()), key="add_news_dir",
        format_func=lambda v: label_of(dictionaries, "direction", v) if v else auto)
    category = st.selectbox(
        "Категория", [""] + dictionaries["directions"].get(direction, []), key="add_news_cat",
        format_func=lambda v: label_of(dictionaries, "category", v) if v else auto)
    news_fmt = format_selector("add_news_fmt")
    if st.button("Загрузить", key="add_news_btn", disabled=not news_url.strip()):
        from src.news.collect import add_single_url

        result = asyncio.run(add_single_url(
            news_url.strip(), direction=direction or None, category=category or None,
            fmt=news_fmt))
        from ui.news_add import describe

        level, msg = describe(result)
        getattr(st, level)(msg)


def render() -> None:
    st.header("Загрузка")
    _render_queue()
    st.divider()
    _render_manual()
    st.divider()
    _render_add_news()

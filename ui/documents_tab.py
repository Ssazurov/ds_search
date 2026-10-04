"""Документы — статус по стадиям сканированием ФС, не отдельной таблицей
(issue #20 п.3, ADR-002 уточнения п.3). Кнопки ingestion в GAR (issue #116,
ADR-006 п.5): пакетная загрузка через src/gar_ingest/documents.py.
Вид таблицы — по образцу «Результатов» через ui/table_utils.py (issue #270)."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

from src.gar_ingest.client import GarPublishError
from src.gar_ingest.documents import ingest_document, revoke_document
from src.gar_ingest.paths import resolve_content_path
from src.metadata.schema import label_of, load_dictionaries
from src.metadata.tags import normalize_tags
from src.news.db import has_published_digest, items_by_source_urls
from ui import notify
from ui.news_add import add_articles_as_news, summarize
from ui.table_utils import COLUMN_LABELS, column_settings, datetime_column, link_column, localize, action_row, table_slots

ROOT = Path(__file__).resolve().parents[1] / "data"
RAW_ROOT = ROOT / "raw"
CLEAN_ROOT = ROOT / "clean"

_ALL = "Все"
_STATUS_ORDER = {"error": 0, "digest_only": 1, "pending": 2, "loaded": 3}  # ошибки сверху
_STATUS_CELL = {
    "loaded": "✅ загружен", "error": "⚠️ ошибка", "pending": "— не загружен",
    # issue #438: отдельная иконка, не путать с pending/error/loaded
    "digest_only": "📑 только пересказ",
}
_STATUS_FILTER = {"pending": "Не загружены", "error": "Ошибка", "loaded": "Загружены"}
_DS_INGESTION_URL = os.environ.get("DS_INGESTION_URL", "http://127.0.0.1:8200")


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
            "summary": meta.get("summary", ""),
            "url": meta.get("source_url") or None,
            "domain": meta.get("source_domain", ""),
            "direction": meta.get("direction", ""),
            "category": meta.get("category", ""),
            "doc_type": meta.get("doc_type", ""),
            "age": meta.get("age", ""),
            "needs_review": meta.get("needs_review"),
            "content_path": meta.get("content_path"),
            "clean": clean_exists,
            "gar_document_id": gar_id,
            "ingest_error": error,
            "status": "loaded" if gar_id else ("error" if error else "pending"),
            # issue #438: ручной сброс авто-статуса digest_only
            "digest_only_dismissed": bool(meta.get("digest_only_dismissed")),
            "added": datetime.fromtimestamp(meta_path.stat().st_mtime),
            "local": True,
        })
    return rows


_FILTER_KEYS = ("doc_filter_text", "doc_filter_status", "doc_filter_doc_type",
                "doc_filter_direction", "doc_filter_local", "doc_filter_gar_status")


def _reset_filters() -> None:
    for k in _FILTER_KEYS:
        st.session_state.pop(k, None)
    version = st.session_state.get("doc_filter_domain_version", 0)
    st.session_state.pop(f"doc_filter_domain_v{version}", None)


_GAR_STATUS_FILTER = {"indexed": "Активные", "archived": "Архив"}

# issue #439: фильтр «Тип документа». "article"/"digest_only" берутся из
# локальных строк (doc_type=article; digest_only — отдельный status,
# см. _apply_digest_only_status), "news"/"digest" существуют только
# как GAR-only строки (_gar_only_rows) — публикуются из src/news/publish.py.
_DOC_TYPE_FILTER = {
    "article": "Статья",
    "digest_only": "Только пересказ (digest_only)",
    "news": "Новость (только GAR)",
    "digest": "Дайджест (только GAR)",
}

_NEWS_FORMAT_ICON = {"news": "📰", "digest": "📝"}
_NEWS_STATUS_LABEL = {"draft": "черновик", "published": "опубликована", "rejected": "отклонена"}


def _derived_cell(url: str | None, derived: dict[str, dict]) -> str:
    """Бейдж «Производные» (issue ds_search#437): новость/дайджест,
    собранные из этой же статьи (связь по source_url, не по gar_document_id —
    у производных свой отдельный документ в GAR)."""
    item = derived.get(url) if url else None
    if not item:
        return ""
    icon = _NEWS_FORMAT_ICON.get(item["format"], "📰")
    return f"{icon} #{item['id']} {_NEWS_STATUS_LABEL.get(item['status'], item['status'])}"


def _apply_digest_only_status(rows: list[dict], derived: dict[str, dict]) -> None:
    """issue #438: статус digest_only для статьи-источника — выставляется,
    когда у документа (doc_type=article) нет своего gar_document_id, но по
    тому же source_url есть опубликованная новость/дайджест (derived — из
    items_by_source_urls). Снимается вручную флагом digest_only_dismissed
    в sidecar .json (см. _render_metadata_form)."""
    for r in rows:
        if r["gar_document_id"] or r["doc_type"] != "article" or r.get("digest_only_dismissed"):
            continue
        item = derived.get(r["url"]) if r["url"] else None
        if item and item["status"] == "published":
            r["status"] = "digest_only"


def _apply_filters(rows: list[dict]) -> list[dict]:
    dictionaries = load_dictionaries()
    directions = sorted({r["direction"] for r in rows if r["direction"]})
    domain_counts = Counter(r["domain"] for r in rows if r["domain"])
    total_count = len(rows)
    domain_list = [_ALL, *sorted(domain_counts, key=lambda d: (-domain_counts[d], d))]
    dom_w = min(max(len(d) for d in domain_list) * 9 + 90, 380)
    with st.container(key="cmpv_docs"):
        c1, c4, c3, c9, c8 = st.columns(5)
        text = c1.text_input("Поиск (название/домен)", key="doc_filter_text").strip().lower()
        domain_key = f"doc_filter_domain_v{st.session_state.get('doc_filter_domain_version', 0)}"
        domain = c4.selectbox(
            "Домен", domain_list, key=domain_key, width=dom_w,
            format_func=lambda d: f"Все ({total_count})" if d == _ALL else f"{d} ({domain_counts[d]})")
        doc_type_filter = c3.selectbox(
            "Тип документа", [_ALL, *_DOC_TYPE_FILTER], key="doc_filter_doc_type", width=240,
            format_func=lambda v: _DOC_TYPE_FILTER.get(v, _ALL))
        with c9.popover("⚙️", help="Дополнительные фильтры"):
            status = st.selectbox(
                "В GAR", [_ALL, *_STATUS_FILTER], key="doc_filter_status",
                format_func=lambda v: _STATUS_FILTER.get(v, _ALL))
            direction = st.selectbox(
                "Направление", [_ALL, *directions], key="doc_filter_direction",
                format_func=lambda v: v if v == _ALL else label_of(dictionaries, "direction", v))
            local = st.selectbox("Локально", [_ALL, "Да", "Нет"], key="doc_filter_local")
            gar_status = st.selectbox(
                "Статус GAR", [_ALL, *_GAR_STATUS_FILTER], key="doc_filter_gar_status",
                format_func=lambda v: _GAR_STATUS_FILTER.get(v, _ALL))
        c8.button("Сбросить", key="doc_filters_reset_btn", on_click=_reset_filters)
    filtered = rows
    if text:
        filtered = [r for r in filtered if text in r["title"].lower() or text in r["domain"].lower()]
    if status != _ALL:
        filtered = [r for r in filtered if r["status"] == status]
    # issue #439: "article" исключает digest_only (отдельный пункт фильтра),
    # чтобы «Статья» и «Только пересказ» не пересекались.
    if doc_type_filter == "article":
        filtered = [r for r in filtered if r["doc_type"] == "article" and r["status"] != "digest_only"]
    elif doc_type_filter == "digest_only":
        filtered = [r for r in filtered if r["status"] == "digest_only"]
    elif doc_type_filter in ("news", "digest"):
        filtered = [r for r in filtered if r["doc_type"] == doc_type_filter]
    if domain != _ALL:
        filtered = [r for r in filtered if r["domain"] == domain]
    if direction != _ALL:
        filtered = [r for r in filtered if r["direction"] == direction]
    if local == "Да":
        filtered = [r for r in filtered if r["local"]]
    elif local == "Нет":
        filtered = [r for r in filtered if not r["local"]]
    # Фильтр «Статус GAR» работает точно только после нажатия «Обновить список GAR» —
    # до этого gar_status у всех строк с gar_document_id будет None и под
    # «Активные»/«Архив» они не попадут (ожидаемо, не баг).
    if gar_status != _ALL:
        filtered = [r for r in filtered if r.get("gar_status") == gar_status]
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
            "summary": meta.get("summary", ""),
            "url": meta.get("source_url") or None,
            "domain": meta.get("source_domain", ""),
            "direction": meta.get("direction", ""),
            "category": meta.get("category", ""),
            "doc_type": doc.get("doc_type", ""),
            "age": meta.get("age", ""),
            "needs_review": meta.get("needs_review"),
            "content_path": None,
            "clean": False,
            "gar_document_id": doc_id,
            "ingest_error": None,
            "status": "loaded",
            "added": None,
            "local": False,
            "gar_status": doc.get("status"),
        })
    return extra


def _row_label(row: dict) -> str:
    """Название документа для сообщений (не технический id)."""
    return row.get("title") or row["doc_id"]


def _has_published_digest_for_url(url: str) -> bool:
    """Проверка наличия опубликованного пересказа для source_url (issue #427)."""
    try:
        return has_published_digest(url)
    except Exception:  # noqa: BLE001 — деградируем, не роняем UI
        return False


def _delete_local_only(row: dict) -> None:
    """Удаляет локальные файлы документа: raw meta + content + clean sidecar.
    Вызывать только когда doc_json_path is not None (issue #299)."""
    meta = json.loads(row["doc_json_path"].read_text(encoding="utf-8"))
    content_path = meta.get("content_path")
    if content_path and Path(content_path).exists():
        Path(content_path).unlink()
    clean_path = CLEAN_ROOT / row["doc_json_path"].parent.name / f"{row['doc_id']}.json"
    if clean_path.exists():
        clean_path.unlink()
    row["doc_json_path"].unlink(missing_ok=True)


def _delete_from_gar_batch(rows: list[dict]) -> None:
    """Удаляет документы из GAR, не трогая локальные файлы (issue #299).
    После успешного удаления сбрасывает gar_document_id в локальном
    sidecar .json, иначе _scan_raw() продолжает считать документ
    загруженным (галочка «В GAR» остаётся — issue #111)."""
    from src.gar_ingest.client import GarIngestClient, GarPublishError, load_settings
    errors: list[str] = []
    settings = load_settings()
    with GarIngestClient(settings) as client:
        for row in rows:
            try:
                client.delete_document(row["gar_document_id"])
            except GarPublishError as exc:
                errors.append(f"{_row_label(row)}: {exc}")
            else:
                # документ успешно удалён из GAR — сбрасываем локальный
                # признак, чтобы список отражал реальное состояние
                if row["doc_json_path"] is not None:
                    try:
                        _update_document_metadata(
                            row["doc_json_path"], {"gar_document_id": None, "ingest_error": None})
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"{_row_label(row)}: не удалось сбросить локальный статус: {exc}")
    notify.report_batch("Удалено из GAR", len(rows) - len(errors), len(rows), errors)
    try:
        st.session_state["gar_docs_cache"] = _fetch_gar_documents()
    except Exception:  # noqa: BLE001
        st.session_state.pop("gar_docs_cache", None)
    st.rerun()


def _delete_everywhere_batch(rows: list[dict]) -> None:
    """Удаляет документы везде: из GAR (если есть) и локально (если есть).
    Issue #299: не прерываем обработку при ошибке в GAR."""
    from src.gar_ingest.client import GarIngestClient, GarPublishError, load_settings
    errors: list[str] = []
    settings = load_settings()
    with GarIngestClient(settings) as client:
        for row in rows:
            # удалить в GAR, если есть
            if row["gar_document_id"]:
                try:
                    client.delete_document(row["gar_document_id"])
                except GarPublishError:  # noqa: PERF203
                    pass  # ожидаемо — документа уже нет в GAR, продолжаем к локальному
            # удалить локально, если есть
            if row["doc_json_path"] is not None:
                try:
                    _delete_local_only(row)
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"{_row_label(row)}: {exc}")
    notify.report_batch("Удалено везде", len(rows) - len(errors), len(rows), errors)
    try:
        st.session_state["gar_docs_cache"] = _fetch_gar_documents()
    except Exception:  # noqa: BLE001
        st.session_state.pop("gar_docs_cache", None)
    st.rerun()


def _confirm_and_run(flag_key: str, warning: str, on_confirm) -> None:
    """Подтверждение необратимой операции (issue #299)."""
    if st.session_state.get(flag_key):
        notify.report("warning", warning)
        cc1, cc2 = st.columns(2)
        if cc1.button("Да, удалить", key=f"{flag_key}_yes"):
            st.session_state[flag_key] = False
            on_confirm()
        if cc2.button("Отмена", key=f"{flag_key}_no"):
            st.session_state[flag_key] = False
            st.rerun()


def _revoke_document_ui(row: dict) -> None:
    """Отзыв корпусного документа из GAR (issue #427).

    Hard delete при наличии прав, иначе fallback на archive. Обновляет
    sidecar .json, проставляя content_status=revoked и gar_document_id=None.
    """
    try:
        result = revoke_document(row["doc_json_path"])
        if result.get("skipped"):
            notify.report("info", f"Документ не был в GAR: {_row_label(row)}")
        else:
            verb = "Архивирован (нет прав на удаление)" if result.get("archived_fallback") else "Отозван из GAR"
            notify.report("success", f"{verb}: {_row_label(row)}")
            st.session_state.pop("gar_docs_cache", None)
    except GarPublishError as exc:
        notify.report("error", f"Не удалось отозвать: {_row_label(row)}", details=[str(exc)])
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


_RECRAWL_TIMEOUT_S = 30  # общий лимит перекачки источника при reload
_RECRAWL_POLL_S = 5      # период обновления статуса в UI


def _refresh_local_content(document_id: str) -> None:
    """ds_ingestion#40: краулера нет в контейнере ds-ingestion, поэтому
    перекачиваем источник здесь (ds-search имеет crawl4ai) во временную папку
    и подменяем только контент рядом с sidecar .json; метаданные не трогаем."""
    import asyncio
    import json as _json
    import shutil
    import tempfile
    from pathlib import Path

    from src.discovery.download import DEFAULT_DATA_ROOT, DownloadError, download_single

    headers = {}
    api_key = os.environ.get("DS_INGESTION_API_KEY")
    if api_key:
        headers["X-Ingestion-Key"] = api_key
    r = httpx.post(f"{_DS_INGESTION_URL}/resolve_by_gar_id",
                   json={"gar_document_id": document_id}, headers=headers, timeout=60)
    if r.status_code != 200:
        return  # reload ниже вернёт понятную ошибку
    ref = r.json()
    jp = Path(DEFAULT_DATA_ROOT) / ref["source"] / f"{ref['doc_id']}.json"
    try:
        meta = _json.loads(jp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GarPublishError(f"reload {document_id}: не прочитан sidecar {jp.name}: {exc}") from exc
    url = meta.get("source_url") or meta.get("canonical_url")
    if not url:
        raise GarPublishError(f"reload {document_id}: в sidecar нет source_url")
    import concurrent.futures as _cf

    async def _dl(tmp_root):
        return await asyncio.wait_for(
            download_single({"url": url}, data_root=tmp_root, dest_dir="r", filename="r"),
            timeout=_RECRAWL_TIMEOUT_S,
        )

    with tempfile.TemporaryDirectory() as tmp, _cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(asyncio.run, _dl(Path(tmp)))
        status = st.empty()
        waited = 0
        while not _cf.wait([fut], timeout=_RECRAWL_POLL_S)[0]:
            waited += _RECRAWL_POLL_S
            status.caption(f"Скачивание источника… {waited} с из {_RECRAWL_TIMEOUT_S}")
        status.empty()
        try:
            new = fut.result()
        except asyncio.TimeoutError as exc:
            raise GarPublishError(
                f"reload {document_id}: источник не ответил за {_RECRAWL_TIMEOUT_S} с") from exc
        except DownloadError as exc:
            raise GarPublishError(f"reload {document_id}: источник недоступен для перекачки ({exc})") from exc
        src = Path(new["content_path"])
        dst = jp.with_suffix(src.suffix)
        if not dst.is_file():
            raise GarPublishError(f"reload {document_id}: тип контента источника изменился ({src.suffix})")
        tmp_dst = dst.with_name(dst.name + ".tmp")
        shutil.copyfile(src, tmp_dst)
        os.replace(tmp_dst, dst)


def _refresh_local_content_for_row(row: dict) -> None:
    """Перекачка контента для документа без gar_document_id (issue #300
    расширение): тот же приём, что в _refresh_local_content, но без
    resolve_by_gar_id — sidecar .json и source_url уже есть локально."""
    import asyncio
    import concurrent.futures as _cf
    import shutil
    import tempfile

    from src.discovery.download import DownloadError, download_single

    jp = row["doc_json_path"]
    url = row.get("url")
    if not url:
        raise GarPublishError(f"reload {row['doc_id']}: в sidecar нет source_url")

    async def _dl(tmp_root):
        return await asyncio.wait_for(
            download_single({"url": url}, data_root=tmp_root, dest_dir="r", filename="r"),
            timeout=_RECRAWL_TIMEOUT_S,
        )

    with tempfile.TemporaryDirectory() as tmp, _cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(asyncio.run, _dl(Path(tmp)))
        status = st.empty()
        waited = 0
        while not _cf.wait([fut], timeout=_RECRAWL_POLL_S)[0]:
            waited += _RECRAWL_POLL_S
            status.caption(f"Скачивание источника… {waited} с из {_RECRAWL_TIMEOUT_S}")
        status.empty()
        try:
            new = fut.result()
        except asyncio.TimeoutError as exc:
            raise GarPublishError(f"reload {row['doc_id']}: источник не ответил за {_RECRAWL_TIMEOUT_S} с") from exc
        except DownloadError as exc:
            raise GarPublishError(f"reload {row['doc_id']}: источник недоступен для перекачки ({exc})") from exc
        src = Path(new["content_path"])
        dst = jp.with_suffix(src.suffix)
        if not dst.is_file():
            raise GarPublishError(f"reload {row['doc_id']}: тип контента источника изменился ({src.suffix})")
        tmp_dst = dst.with_name(dst.name + ".tmp")
        shutil.copyfile(src, tmp_dst)
        os.replace(tmp_dst, dst)


def _reload_from_source(document_id: str) -> dict:
    """POST /reload_by_gar_id на ds_ingestion (issue ds_search#145 /
    ADR-0007): полная перезагрузка metadata+content из локального источника.
    Auth: X-Ingestion-Key, см. ADR-0008."""
    headers = {}
    api_key = os.environ.get("DS_INGESTION_API_KEY")
    if api_key:
        headers["X-Ingestion-Key"] = api_key
    _refresh_local_content(document_id)
    resp = httpx.post(
        f"{_DS_INGESTION_URL}/reload_by_gar_id",
        json={"gar_document_id": document_id, "recrawl": False}, headers=headers, timeout=120,
    )
    if resp.status_code != 200:
        raise GarPublishError(f"reload {document_id} failed: {resp.status_code} {resp.text}")
    return resp.json()


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
        notify.report("warning", "Справочник направлений GAR недоступен", details=[f"{exc}", "direction/category временно не редактируются"])

    loaded_count = sum(1 for r in selected_rows if r["gar_document_id"])

    # автоподстановка direction/category/age/needs_review при смене состава выбора
    # (issue #336): для единичного выбора — всегда брать значения документа,
    # для множественного — общее значение (если валидно) или пусто
    sel_key = tuple(sorted(r["doc_id"] for r in selected_rows))
    # #345: ключи batch_* удаляются Streamlit, если форма не рисовалась в прогоне
    # (например, после удаления из GAR) — тогда автоподстановку надо повторить
    if (st.session_state.get("_batch_meta_sel_key") != sel_key
            or "batch_direction" not in st.session_state):
        # Инициализация ключей, если их нет
        if "batch_age" not in st.session_state:
            st.session_state["batch_age"] = ""
        if "batch_needs_review" not in st.session_state:
            st.session_state["batch_needs_review"] = "не менять"

        if len(selected_rows) == 1:
            # Единичный выбор: всегда брать значения документа
            doc = selected_rows[0]
            st.session_state["batch_direction"] = doc.get("direction", "")
            st.session_state["batch_category"] = doc.get("category", "")
            st.session_state["batch_age"] = doc.get("age", "")

            # needs_review — bool в метаданных, но selectbox работает с текстом
            needs_review = doc.get("needs_review")
            if needs_review is True:
                st.session_state["batch_needs_review"] = "да"
            elif needs_review is False:
                st.session_state["batch_needs_review"] = "нет"
            else:
                st.session_state["batch_needs_review"] = "не менять"
        else:
            # Множественный выбор: общее значение (если валидно) или пусто
            dirs = {r["direction"] for r in selected_rows}
            common_dir = next(iter(dirs)) if len(dirs) == 1 else ""
            st.session_state["batch_direction"] = common_dir if common_dir in directions else ""

            cats = {r["category"] for r in selected_rows}
            common_cat = next(iter(cats)) if len(cats) == 1 else ""
            valid_cats = category_options_for_direction(gar_fields, common_dir) if common_dir and gar_fields else []
            st.session_state["batch_category"] = common_cat if common_cat in valid_cats else ""

            st.session_state["batch_age"] = ""
            st.session_state["batch_needs_review"] = "не менять"

        st.session_state["_batch_meta_sel_key"] = sel_key

    # Без st.form: внутри st.form виджеты не вызывают rerun при изменении
    # (только по submit), поэтому список категорий не пересчитывался бы под
    # новое направление (issue #304). Обычные виджеты + обычная кнопка вместо
    # формы — заодно нет рамки, отделяющей «Направление» от остальных полей.
    st.divider()
    st.write("**Пакетное редактирование выбранных документов**")
    st.caption(f"Выбрано: {len(selected_rows)}, из них уже в GAR: {loaded_count} (для них уйдёт PATCH в GAR)")
    direction = ""
    if directions:
        direction = st.selectbox(
            "Направление", [""] + directions, key="batch_direction",
            format_func=lambda v: v if not v else dir_labels.get(v, v))
    category = ""
    if directions:
        if direction:
            categories = category_options_for_direction(gar_fields, direction)
            cat_labels = option_labels(gar_fields).get("category", {})
            category = st.selectbox(
                "Категория", [""] + categories, key="batch_category",
                format_func=lambda v: v if not v else cat_labels.get(v, v))
        else:
            st.caption("Категория — сначала выберите направление")
    age = st.selectbox("Возраст (Age)", [""] + AGE_OPTIONS, key="batch_age")
    tags_input = st.text_input(
        "Теги (через запятую)", key="batch_tags",
        help="Заменяет текущие tags у всех выбранных документов целиком. Пусто — не менять.")
    needs_review_choice = st.selectbox(
        "Требует проверки (Needs review)", ["не менять", "да", "нет"], key="batch_needs_review")

    one = selected_rows[0] if len(selected_rows) == 1 else None
    show_revoke = bool(one and one.get("url") and _has_published_digest_for_url(one["url"]))
    cols = action_row(1 + bool(one) + show_revoke, "doc_batch_apply")
    i = 0
    if one:
        if cols[i].button("🔄 Перезагрузить из источника", key="doc_reload_btn"):
            _reload_from_source_ui(one)
        i += 1
    if show_revoke:
        if cols[i].button("📤 Снять полный текст", key="doc_revoke_btn",
                          help="Отозвать оригинал из GAR (опубликован пересказ)"):
            st.session_state["confirm_revoke_document"] = True
            st.rerun()
        i += 1
    if cols[i].button("Применить к выбранным", key="batch_metadata_apply_btn"):
        updates = {}
        if direction:
            updates["direction"] = direction
        if category:
            updates["category"] = category
        if age:
            updates["age"] = age
        if tags_input.strip():
            updates["tags"] = normalize_tags(tags_input)
        if needs_review_choice != "не менять":
            updates["needs_review"] = needs_review_choice == "да"

        if not updates:
            notify.report("info", "Ничего не выбрано для изменения")
        else:
            errors = []
            for row in selected_rows:
                try:
                    if row["doc_json_path"] is not None:
                        _update_document_metadata(row["doc_json_path"], updates)
                    if row["gar_document_id"]:
                        _patch_gar_metadata(row["gar_document_id"], updates)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{_row_label(row)}: {exc}")

            notify.report_batch("Обновлено", len(selected_rows) - len(errors), len(selected_rows), errors)
            st.rerun()


def _reload_from_source_ui(row: dict) -> None:
    """issue #300: перезагрузка одного документа из источника."""
    try:
        if row["gar_document_id"]:
            rep = _reload_from_source(row["gar_document_id"])
            changed, preserved = rep.get("changed_fields"), rep.get("preserved_fields")
            notify.report(
                "success", f"Перезагружено из источника: {_row_label(row)}",
                {"изменено полей": len(changed or []), "сохранено полей": len(preserved or []),
                 "контент заменён": "да" if rep.get("content_replaced") else "нет"},
                details=[f"Изменено: {', '.join(map(str, changed))}"] if changed else None)
            st.session_state.pop("gar_docs_cache", None)
        elif row["doc_json_path"] is not None:
            _refresh_local_content_for_row(row)
            notify.report("success", f"Контент перекачан из источника: {_row_label(row)}")
        else:
            notify.report("info", f"Нет ни GAR-документа, ни локального файла: {_row_label(row)}")
        st.rerun()
    except GarPublishError as exc:
        notify.report("error", "Не удалось перезагрузить из источника",
                      details=[f"{_row_label(row)}: {exc}"])


def _archive_batch(rows: list[dict], archive: bool) -> None:
    from src.gar_ingest.client import GarIngestClient, GarPublishError, load_settings
    errors: list[str] = []
    settings = load_settings()
    with GarIngestClient(settings) as client:
        for row in rows:
            try:
                (client.archive_document if archive else client.unarchive_document)(
                    row["gar_document_id"])
            except GarPublishError as exc:
                errors.append(f"{_row_label(row)}: {exc}")
    verb = "Архивировано" if archive else "Возвращено из архива"
    notify.report_batch(verb, len(rows) - len(errors), len(rows), errors)
    # обновить кэш GAR, чтобы фильтр «Статус GAR» (#297) сразу отражал
    # новое состояние без повторного ручного «Обновить список GAR»
    try:
        st.session_state["gar_docs_cache"] = _fetch_gar_documents()
    except Exception:  # noqa: BLE001 — не роняем успешный архив из-за ошибки рефреша
        st.session_state.pop("gar_docs_cache", None)
    st.rerun()


def _resend_batch(rows: list[dict]) -> None:
    """Переотправка исправленного локального md в GAR: отзыв старого документа + повторная загрузка."""
    progress = st.progress(0.0, text=f"0/{len(rows)}")
    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        try:
            revoke_document(row["doc_json_path"])
            ingest_document(row["doc_json_path"])
        except Exception as exc:  # noqa: BLE001 — не роняем весь батч на одной ошибке
            errors.append(f"{_row_label(row)}: {exc} (если документа нет в GAR — «Загрузить в GAR»)")
        progress.progress(i / len(rows), text=f"{i}/{len(rows)}")
    notify.report_batch("Переотправлено в GAR", len(rows) - len(errors), len(rows), errors)
    try:
        st.session_state["gar_docs_cache"] = _fetch_gar_documents()
    except Exception:  # noqa: BLE001
        st.session_state.pop("gar_docs_cache", None)
    st.rerun()


def _ingest_batch(rows: list[dict]) -> None:
    pending = [r for r in rows if not r["gar_document_id"]]
    if not pending:
        notify.report("info", "Все выбранные документы уже загружены в GAR")
        return
    progress = st.progress(0.0, text=f"0/{len(pending)}")
    errors: list[str] = []
    for i, row in enumerate(pending, start=1):
        try:
            ingest_document(row["doc_json_path"])
        except Exception as exc:  # noqa: BLE001 — не роняем весь батч на одной ошибке
            errors.append(f"{_row_label(row)}: {exc}")
        progress.progress(i / len(pending), text=f"{i}/{len(pending)}")
    notify.report_batch("Загружено в GAR", len(pending) - len(errors), len(pending), errors)
    st.rerun()


def _to_news_batch(rows: list[dict], fmt: str = "news") -> None:
    """«В новости» (issue #398): LLM-черновики по source_url выбранных документов.
    Как в «Результатах», но без смены статуса (у документов его нет)."""
    with_url = [r for r in rows if r.get("url")]
    errors = [f"{_row_label(r)}: нет source_url" for r in rows if not r.get("url")]
    stats: dict[str, int] = {}
    ok = 0
    if with_url:
        with st.spinner(f"Генерация черновиков: {len(with_url)}…"):
            results = add_articles_as_news(
                [{"url": r["url"], "title": r.get("title") or ""} for r in with_url], fmt=fmt)
        outcome = summarize(results)
        ok, stats = outcome.ok, outcome.stats
        errors = outcome.errors + errors
    notify.report(notify.outcome_level(ok, len(rows)),
                  f"Добавлено в новости: {ok} из {len(rows)}", stats, errors)
    st.rerun()


def _render_recrawl_batch() -> None:
    """ds_search#457: пакетная перекачка статей downsideup.org из источника."""
    from src.recrawl.batch import run_batch, scan_candidates, load_state

    with st.expander("🔄 Пакетная перекачка из источника (downsideup.org)"):
        cands = scan_candidates("downsideup.org")
        state = load_state()
        done = sum(1 for r in cands if state.get(r["doc_id"], {}).get("status") == "done")
        failed = sum(1 for r in cands if state.get(r["doc_id"], {}).get("status") == "failed")
        st.caption(f"В GAR: {len(cands)}, перекачано: {done}, с ошибкой: {failed}. "
                   "Заменяет контент как кнопка «Перезагрузить из источника». Старый файл → data/recrawl_backup.")
        limit = st.number_input("Размер порции", min_value=1, max_value=50, value=3, key="recrawl_limit")
        retry = st.checkbox("Повторить ошибочные", key="recrawl_retry")
        if st.button(f"Перекачать порцию ({int(limit)})", key="recrawl_run_btn"):
            bar = st.progress(0.0)
            out = run_batch(int(limit), retry_failed=retry,
                            progress=lambda i, n, t: bar.progress(i / max(n, 1), text=f"{i + 1}/{n}: {t}"))
            bar.empty()
            for r in out["processed"]:
                st.write(f"{'✅' if r['status'] == 'done' else '⚠️'} {r['title']}: "
                         f"{r.get('old_len')} → {r.get('new_len')} симв. {r.get('error', '')}")
            st.caption(f"Отчёт: {out['report']}. Всего перекачано {out['done_total']}/{out['total']}.")
            st.session_state.pop("gar_docs_cache", None)


def render() -> None:
    _render_recrawl_batch()

    rows = _scan_raw()
    # Добавляем gar_status из кэша GAR к локальным строкам (issue #297)
    cache = st.session_state.get("gar_docs_cache") or {}
    for r in rows:
        r["gar_status"] = cache.get(r["gar_document_id"] or "", {}).get("status")
    rows = rows + _gar_only_rows(rows)
    if not rows:
        notify.report("info", "Нет сохранённых документов в data/raw")
        return

    # issue #438: статус digest_only считается до фильтрации/сортировки,
    # чтобы сортировка по статусу и счётчики ниже видели актуальное значение
    derived = items_by_source_urls([r["url"] for r in rows])
    _apply_digest_only_status(rows, derived)

    filtered = _apply_filters(rows)
    if not filtered:
        notify.report("info", "Ничего не найдено по текущим фильтрам")
        return

    labels = {
        **COLUMN_LABELS, "clean": "Очищен", "gar": "В GAR", "error": "Ошибка", "added": "Добавлен",
        "md": "MD", "json": "JSON", "derived": "Производные",
    }

    _HOST_DATA_ROOT = os.environ.get("HOST_DATA_ROOT", "/home/vector/projects/ds/ds_search/data")
    _WSL_DISTRO = os.environ.get("HOST_WSL_DISTRO", "Ubuntu")

    def _resolved_content_path(p, doc_json_path) -> Path | None:
        # issue #445: content_path в sidecar .json бывает контейнерным
        # (/app/data/...) или host-путём другой машины/окружения — в обоих
        # случаях голый Path(p) не существует локально. resolve_content_path
        # (см. src/gar_ingest/paths.py, issue #400) уже умеет падать обратно
        # на файл рядом с sidecar .json (тот же stem, .md/.pdf) — переиспользуем
        # эту же логику здесь, иначе колонка md остаётся пустой при живом файле.
        if not p:
            return None
        resolved = resolve_content_path(doc_json_path, p)
        return resolved if resolved.exists() else None

    def _file_uri(p, doc_json_path) -> str | None:
        # issue #292/#327: vscode://vscode-remote/wsl+<distro>/... — ненадёжно
        # (переоткрытие уже открытого remote-окна фокусирует его, файл не
        # открывается). file://wsl.localhost/... — браузер блокирует
        # ("Not allowed to load local resource"), это подтвердилось.
        # Решение: свой протокол dsdoc:// (зарегистрирован в реестре хоста,
        # HKCU\Software\Classes\dsdoc -> открывает файл по default handler'у
        # расширения через \\wsl.localhost\<distro>\<path> — у автора это
        # Notepad++). Требует host path, см. HOST_DATA_ROOT.
        # Статика Streamlit (issue #325) оставлена как fallback ниже.
        resolved = _resolved_content_path(p, doc_json_path)
        if resolved is None:
            return None
        try:
            rel = resolved.relative_to(ROOT)
        except ValueError:
            return None
        return f"dsdoc://{_WSL_DISTRO}{_HOST_DATA_ROOT}/{rel.as_posix()}"

    def _static_uri(p, doc_json_path) -> str | None:
        # Fallback для тех, у кого нет VS Code/Remote-WSL — статика Streamlit
        # (data смонтирован ещё раз в /app/ui/static/data, НЕ symlink'ом:
        # у symlink'а realpath уходит за пределы app_static_root, и Streamlit
        # отвечает 400 Bad Request на любой файл — issue #325).
        resolved = _resolved_content_path(p, doc_json_path)
        if resolved is None:
            return None
        try:
            rel = resolved.relative_to(ROOT)
        except ValueError:
            return None
        return f"http://localhost:8503/app/static/data/{rel.as_posix()}"

    df = pd.DataFrame([
        {
            "title": r["title"], "url": r["url"], "domain": r["domain"],
            "direction": r["direction"], "category": r["category"], "doc_type": r["doc_type"],
            "clean": r["clean"], "gar": _STATUS_CELL[r["status"]],
            "error": r["ingest_error"] or "", "added": r["added"],
            "md": _file_uri(r["content_path"], r["doc_json_path"]),
            "json": _file_uri(r["doc_json_path"], r["doc_json_path"]),
            "derived": _derived_cell(r["url"], derived),
        }
        for r in filtered
    ])
    df.insert(0, "select", False)

    # Кнопка "Колонки" и "Обновить список из GAR" в одной строке
    with st.container(key="cmp_garrow"):
        col_gar_refresh, col_gar_info = st.columns(2)
    tbl, cap_col, gear_col = table_slots("documents")
    order, config, sort = column_settings(
        "documents", {k: labels[k] for k in ("select", "title", "url", "domain", "direction", "category",
                                             "doc_type", "clean", "gar", "error", "derived", "added",
                                             "md", "json")},
        {labels["url"]: link_column(), labels["added"]: datetime_column(labels["added"]),
         labels["md"]: st.column_config.LinkColumn(
             labels["md"], display_text=":material/description:", width="small"),
         labels["json"]: st.column_config.LinkColumn(
             labels["json"], display_text=":material/data_object:", width="small")}, host=gear_col)
    if col_gar_refresh.button("Обновить список из GAR", key="gar_docs_refresh_btn"):
        try:
            st.session_state["gar_docs_cache"] = _fetch_gar_documents()
        except Exception as exc:  # noqa: BLE001 — сеть/GAR недоступны, не роняем вкладку
            notify.report("error", "Не удалось обновить список из GAR", details=[str(exc)])
        else:
            # Форсируем remount selectbox'а "Домен" новым key, иначе Streamlit
            # не обновляет отображаемый текст закрытого списка (только после
            # открытия dropdown) — см. отчёт пользователя от 2026-09-27.
            st.session_state["doc_filter_domain_version"] = (
                st.session_state.get("doc_filter_domain_version", 0) + 1
            )
            st.rerun()
    if "gar_docs_cache" in st.session_state:
        col_gar_info.caption(
            f"GAR-документов в кэше: {len(st.session_state['gar_docs_cache'])} "
            "(обновляется по кнопке, issue #295)"
        )
    else:
        col_gar_info.caption("Список GAR ещё не загружен — нажмите «Обновить список из GAR», "
                             "чтобы увидеть документы без локального файла")

    df_display = localize(df).rename(columns=labels)
    if sort:
        df_display = df_display.sort_values(sort[0], ascending=sort[1])
    edited = tbl.data_editor(
        df_display, hide_index=True, width="stretch",
        disabled=[c for c in labels.values() if c != labels["select"]], key="doc_table_editor",
        column_order=order, column_config=config,
    )
    selected_rows = [filtered[i] for i in edited.index[edited[labels["select"]]]]
    cap_col.caption(
        f"Всего: {len(df)}, очищено: {int(df['clean'].sum())}, "
        f"в GAR: {sum(r['status'] == 'loaded' for r in filtered)}, выбрано: {len(selected_rows)}"
    )

    # issue #299: кнопки удаления с явной семантикой и подтверждением
    not_loaded = [r for r in selected_rows if not r["gar_document_id"]]
    gar_only = [r for r in selected_rows if r["gar_document_id"]]
    all_have_gar = len(gar_only) == len(selected_rows) and selected_rows
    archivable = [r for r in selected_rows if r["gar_document_id"]]
    resendable = [r for r in gar_only if r.get("doc_json_path") and r.get("content_path")]

    # Кнопки прижаты к правому краю
    with_url = [r for r in selected_rows if r.get("url")]
    # Порядок кнопок (issue #432): статусные действия → две кнопки генерации
    # черновика «В пересказ» / «В новости» справа, без переключателя «Формат».
    b1, b8, b2, b3, b4, b5, b6, b7 = action_row(8, "documents")
    if b1.button(f"Загрузить в GAR ({len(not_loaded)})", disabled=not not_loaded,
                 key="ingest_selected_btn"):
        _ingest_batch(not_loaded)
    if b8.button(f"Переотправить в GAR ({len(resendable)})", disabled=not resendable,
                 key="resend_to_gar_btn",
                 help="Заменить документ в GAR текущим локальным md (старый отзывается, затем грузится заново)"):
        _resend_batch(resendable)
    if b2.button(f"Удалить из GAR ({len(gar_only)})", disabled=not all_have_gar,
                 key="delete_from_gar_btn"):
        st.session_state["confirm_delete_from_gar"] = True
        st.rerun()
    if b3.button(f"Удалить везде ({len(selected_rows)})", disabled=not selected_rows,
                 key="delete_everywhere_btn"):
        st.session_state["confirm_delete_everywhere"] = True
        st.rerun()
    if b4.button(f"Архивировать ({len(archivable)})",
                 disabled=not archivable, key="doc_archive_btn"):
        _archive_batch(archivable, archive=True)
    if b5.button(f"Из архива ({len(archivable)})",
                 disabled=not archivable, key="doc_unarchive_btn"):
        _archive_batch(archivable, archive=False)
    if b6.button(f"В пересказ ({len(with_url)})", disabled=not with_url, key="doc_to_digest_btn",
                 help="LLM-черновик сокращённого пересказа со ссылкой на источник → вкладка "
                      "«Новости»; публикация только после чеклиста"):
        _to_news_batch(with_url, fmt="digest")
    if b7.button(f"В новости ({len(with_url)})", disabled=not with_url, key="doc_to_news_btn",
                 help="LLM-черновик новости по выбранным документам → вкладка «Новости»"):
        _to_news_batch(with_url, fmt="news")

    _confirm_and_run(
        "confirm_delete_from_gar",
        f"⚠️ Будет удалено {len(gar_only)} документов из GAR. Локальные файлы останутся. Операция необратима.",
        lambda: _delete_from_gar_batch(gar_only))
    _confirm_and_run(
        "confirm_delete_everywhere",
        f"⚠️ Будет удалено {len(selected_rows)} документов везде (из GAR и локально). Операция необратима.",
        lambda: _delete_everywhere_batch(selected_rows))

    # issue #427: подтверждение отзыва документа после публикации пересказа
    if st.session_state.get("confirm_revoke_document") and len(selected_rows) == 1:
        row = selected_rows[0]
        notify.report("warning", f"⚠️ Будет отозван из GAR: {_row_label(row)}. "
                                 "Пересказ останется опубликованным. Операция необратима.")
        cc1, cc2 = st.columns(2)
        if cc1.button("Да, снять полный текст", key="confirm_revoke_yes"):
            st.session_state["confirm_revoke_document"] = False
            _revoke_document_ui(row)
        if cc2.button("Отмена", key="confirm_revoke_no"):
            st.session_state["confirm_revoke_document"] = False
            st.rerun()

    # issue #286: форма редактирования метаданных перед публикацией
    if selected_rows:
        _render_metadata_form(selected_rows)

        # issue #438: ручной сброс авто-статуса digest_only — на случай,
        # если всё же нужно догрузить полный текст статьи в GAR
        if len(selected_rows) == 1 and selected_rows[0]["status"] == "digest_only" \
                and selected_rows[0]["doc_json_path"] is not None:
            row = selected_rows[0]
            if st.button("♻️ Снять digest_only (догрузить полный текст)", key="doc_digest_only_dismiss_btn",
                         help="Статья помечена как «только пересказ» — есть опубликованная новость/"
                              "дайджест по этому source_url. Снимите, если всё же нужно загрузить "
                              "полный текст статьи в GAR."):
                _update_document_metadata(row["doc_json_path"], {"digest_only_dismissed": True})
                notify.report("success", f"Статус digest_only снят: {_row_label(row)}")
                st.rerun()


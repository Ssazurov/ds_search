"""Источники/домены — CRUD config/licenses.yaml + агрегация discovered_sources
по домену (issue #20 п.4, ADR-002: "это config/licenses.yaml, не новая таблица").

UI: список доменов слева (фильтры, поиск, пагинация 10/20/50), форма выбранного
домена справа (master-detail)."""
from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path

import streamlit as st
import yaml

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from src.license.checker import (
    default_attribution_template,
    PUBLISH_PERMISSION_LABELS, LicenseStatus, PublishPermission, _CONFIG_PATH,
    normalize_domain, parse_publish_permission,
)

_STATUSES = [s.value for s in LicenseStatus if s != LicenseStatus.PENDING_MANUAL_REVIEW]
_PERMISSIONS = [p.value for p in PublishPermission]
# Значения в licenses.yaml остаются английскими (контракт с checker), русские — только для UI.
STATUS_LABELS = {
    "allow": "Разрешено",
    "attribution_required": "Разрешено со ссылкой на источник",
    "deny": "Запрещено",
}
_PAGE_SIZES = [10, 20, 50]
_FILTERS = {"all": "Все", "pending": "Не проверен", "found": "Есть находки", "agg": "Агрегаторы"}
_ATTR_EXAMPLE = "Источник: {title} ({source_url}), Агентство социальной информации (asi.org.ru)"


def _load_registry() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _save_registry(registry: dict) -> None:
    _CONFIG_PATH.write_text(
        "# Реестр лицензий/ToS источников (issue #3, ADR-001 п.3).\n"
        + yaml.safe_dump(registry, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )


def _domain_counts() -> Counter:
    settings = load_settings()
    try:
        with GarDiscoveryClient(settings) as client:
            rows = client.list_discovered_sources()
    except Exception:  # noqa: BLE001
        return Counter()
    return Counter(normalize_domain(r["domain"]) for r in rows
                   if r.get("domain") and r.get("status") != "rejected")


def _dismiss_domain(domain: str) -> None:
    """Удаление домена: находки в GAR переводим в rejected (DELETE-эндпоинта нет),
    _domain_counts их не считает — домен исчезает из списка."""
    with GarDiscoveryClient(load_settings()) as client:
        for r in client.list_discovered_sources():
            if (r.get("domain") and normalize_domain(r["domain"]) == domain
                    and r.get("status") != "rejected"):
                client.update_discovered_source(r["id"], status="rejected")


def build_rows(registry: dict, counts: Counter) -> list[dict]:
    """Строки списка: сначала непроверенные с находками, затем по числу находок и алфавиту."""
    rows = []
    for domain in set(registry) | set(counts):
        entry = registry.get(domain, {})
        rows.append({
            "domain": domain,
            "count": counts.get(domain, 0),
            "pending": entry.get("status") not in _STATUSES,
            "aggregator": bool(entry.get("is_aggregator")),
            "status": entry.get("status"),
        })
    rows.sort(key=lambda r: (not (r["pending"] and r["count"]), not r["pending"], -r["count"], r["domain"]))
    return rows


def filter_rows(rows: list[dict], flt: str, query: str) -> list[dict]:
    q = query.strip().lower()
    out = [r for r in rows if q in r["domain"]]
    if flt == "pending":
        out = [r for r in out if r["pending"]]
    elif flt == "found":
        out = [r for r in out if r["count"] > 0]
    elif flt == "agg":
        out = [r for r in out if r["aggregator"]]
    return out


def _row_label(r: dict) -> str:
    mark = "🟡" if r["pending"] else ("🔴" if r["status"] == "deny" else "🟢")
    tail = " 🔁" if r["aggregator"] else ""
    return f"{mark} {r['domain']}{tail} · {r['count']}"


def _render_add_news() -> None:
    st.caption("Штатная загрузка одной новости по URL (issue #183) — та же "
               "проверка лицензии домена и LLM-классификация, что и автосбор.")
    news_url = st.text_input("Ссылка на новость", key="add_news_url")
    if st.button("Добавить новость", disabled=not news_url.strip()):
        from src.news.collect import add_single_url

        result = asyncio.run(add_single_url(news_url.strip()))
        level, msg = {
            "drafted": ("success", "Добавлено черновиком в news_items (needs_review)"),
            "skipped_duplicate": ("info", "Такая ссылка уже есть в news_items"),
            "license_denied": ("warning", "Домен не прошёл проверку лицензии (issue #3) — проставьте статус выше"),
            "download_failed": ("error", "Не удалось скачать/распарсить страницу"),
            "llm_failed": ("error", "LLM не смог собрать черновик по этому тексту (детали — в логе ds-search)"),
            "llm_unavailable": ("error", "LLM недоступен (endpoint/таймаут) — проверьте Ollama и NEWS_LLM_ENDPOINT"),
            "not_relevant": ("info", "LLM счёл новость нерелевантной теме — не добавлено"),
        }.get(result, ("error", result))
        getattr(st, level)(msg)


def _render_detail(domain: str, registry: dict, row: dict) -> None:
    entry = registry.get(domain, {})
    pending = row["pending"]
    head = f"### {domain}"
    if pending:
        head += "  :orange[не проверен]"
    if row["aggregator"]:
        head += "  :violet[агрегатор]"
    st.markdown(head)
    st.caption(f"Находок: {row['count']}")
    status = st.selectbox(
        "Статус", _STATUSES,
        index=_STATUSES.index(entry.get("status")) if not pending else None,
        format_func=STATUS_LABELS.get,
        placeholder="— выбрать —",
        key=f"status_{domain}",
    )
    permission = st.selectbox(
        "Разрешение на публикацию", _PERMISSIONS,
        index=_PERMISSIONS.index(parse_publish_permission(entry.get("publish_permission")).value),
        format_func=lambda v: PUBLISH_PERMISSION_LABELS[PublishPermission(v)],
        key=f"perm_{domain}",
    )
    attribution = st.text_input(
        "Шаблон атрибуции",
        value=entry.get("attribution_template") or default_attribution_template(domain),
        help=f"Доступно: {{title}}, {{source_url}}. Пример: {_ATTR_EXAMPLE}",
        key=f"attr_{domain}",
    )
    notes = st.text_area("Заметки", value=entry.get("notes", ""), key=f"notes_{domain}")
    is_aggregator = st.checkbox(
        "Агрегатор", value=bool(entry.get("is_aggregator", False)), key=f"agg_{domain}",
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Сохранить", key=f"save_{domain}", type="primary", disabled=status is None, width="stretch"):
        registry[domain] = {
            "status": status,
            "attribution_template": attribution or default_attribution_template(domain),
            "notes": notes,
            "checked_date": entry.get("checked_date"),
            "is_aggregator": is_aggregator,
            "publish_permission": permission,
        }
        _save_registry(registry)
        st.rerun()
    if c2.button("Отменить", key=f"cancel_{domain}", width="stretch"):
        for p in ("status", "perm", "attr", "notes", "agg"):
            st.session_state.pop(f"{p}_{domain}", None)
        st.rerun()
    if c3.button("Удалить", key=f"del_{domain}", width="stretch"):
        try:
            _dismiss_domain(domain)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Не удалось убрать находки домена в GAR: {exc}")
            return
        registry.pop(domain, None)
        _save_registry(registry)
        st.session_state.pop("dom_sel", None)
        st.rerun()


def render() -> None:
    st.header("Источники / домены")
    with st.expander("Добавить новость по ссылке"):
        _render_add_news()
    st.caption("Реестр ToS-статусов — config/licenses.yaml (issue #3). "
               "Новые домены попадают сюда автоматически со статусом «не проверен».")
    registry = _load_registry()
    rows = build_rows(registry, _domain_counts())
    by_domain = {r["domain"]: r for r in rows}

    flt = st.radio(
        "Фильтр", list(_FILTERS), horizontal=True, label_visibility="collapsed",
        format_func=lambda k: f"{_FILTERS[k]} · {len(filter_rows(rows, k, ''))}",
    )
    left, right = st.columns([1, 1.4], gap="large")
    with left:
        query = st.text_input("Поиск", placeholder="домен, например unicef.org", label_visibility="collapsed")
        shown = filter_rows(rows, flt, query)
        size = st.selectbox("На странице", _PAGE_SIZES, index=0)
        pages = max(1, -(-len(shown) // size))
        page = st.number_input("Страница", 1, pages, 1) if pages > 1 else 1
        chunk = shown[(page - 1) * size: page * size]
        sel = st.session_state.get("dom_sel")
        if sel not in by_domain and rows:
            sel = st.session_state["dom_sel"] = (chunk or rows)[0]["domain"]
        for r in chunk:
            if st.button(_row_label(r), key=f"pick_{r['domain']}", width="stretch",
                         type="primary" if r["domain"] == sel else "secondary"):
                st.session_state["dom_sel"] = r["domain"]
                st.rerun()
        st.caption(f"{len(shown)} из {len(rows)} · стр. {page} из {pages}")
    with right:
        if sel in by_domain:
            _render_detail(sel, registry, by_domain[sel])
        else:
            st.info("Доменов пока нет")

    st.divider()
    with st.expander("Добавить домен"):
        new_domain = st.text_input("Домен (например, example.org)")
        if st.button("Добавить", disabled=not new_domain.strip()):
            nd = normalize_domain(new_domain)
            registry[nd] = {"status": "pending_manual_review", "notes": "",
                            "attribution_template": default_attribution_template(nd),
                            "publish_permission": PublishPermission.NOT_SET.value}
            _save_registry(registry)
            st.session_state["dom_sel"] = nd
            st.rerun()

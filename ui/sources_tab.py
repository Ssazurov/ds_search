"""Источники/домены — CRUD реестра источников в GAR (ds ADR-0021) + агрегация
discovered_sources по домену (issue #20 п.4, ADR-002).

UI: список доменов слева (фильтры, поиск, пагинация 10/20/50), форма выбранного
домена справа (master-detail)."""
from __future__ import annotations

from collections import Counter

import streamlit as st

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from src.license.registry_store import delete_entry, load_registry, save_entry
from src.license.checker import (
    default_attribution_template,
    PUBLISH_PERMISSION_LABELS, LicenseStatus, PublishPermission,
    normalize_domain, parse_publish_permission,
)
from src.site_publish import runner
from ui import notify

_STATUSES = [s.value for s in LicenseStatus if s != LicenseStatus.PENDING_MANUAL_REVIEW]
_PERMISSIONS = [p.value for p in PublishPermission]
# Значения статуса в GAR остаются английскими (контракт с checker), русские — только для UI.
STATUS_LABELS = {
    "allow": "Разрешено",
    "attribution_required": "Разрешено со ссылкой на источник",
    "deny": "Запрещено",
}
_TYPE_LABELS = {"articles": "Статьи", "news": "Новости", "glossary": "Глоссарий", "links": "Ссылки"}
_PAGE_SIZES = [10, 20, 50]
_FILTERS = {"all": "Все", "pending": "Не проверен", "found": "Есть находки", "agg": "Агрегаторы",
            "community": "Сообщества"}
_SOURCE_TYPES = ["site", "community", "channel"]  # issue #467
_SOURCE_TYPE_LABELS = {"site": "Сайт", "community": "Сообщество VK", "channel": "Канал"}
_ATTR_EXAMPLE = "Источник: {title} ({source_url}), Агентство социальной информации (asi.org.ru)"


def _load_registry() -> dict:
    return load_registry()


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


def build_rows(registry: dict, counts: Counter, stats: dict | None = None) -> list[dict]:
    """Строки списка: сначала непроверенные с находками, затем по числу находок и алфавиту.
    Сообщества (ключ domain/path, issue #473) выводятся сразу под своим доменом (issue #474)."""
    rows = []
    for domain in set(registry) | set(counts):
        entry = registry.get(domain, {})
        is_community = "/" in domain
        rows.append({
            "domain": domain,
            "base": domain.split("/", 1)[0],
            "is_community": is_community,
            "count": counts.get(domain, 0),
            "materials": (stats or {}).get(domain, {}).get("total", 0),
            "mat": (stats or {}).get(domain),
            "pending": entry.get("status") not in _STATUSES,
            "aggregator": bool(entry.get("is_aggregator")),
            "status": entry.get("status"),
            "source_type": entry.get("source_type") or ("community" if is_community else "site"),
        })
    rows.sort(key=lambda r: (not (r["pending"] and r["count"]), not r["pending"], -r["count"], r["domain"]))
    return _group_under_domain(rows)


def _group_under_domain(rows: list[dict]) -> list[dict]:
    """Сохраняет порядок доменов; сообщества переносит сразу после своего домена."""
    bases = {r["domain"] for r in rows if not r["is_community"]}
    out: list[dict] = []
    for r in rows:
        if not r["is_community"] or r["base"] not in bases:
            out.append(r)
            if not r["is_community"]:
                out.extend(c for c in rows if c["is_community"] and c["base"] == r["domain"])
    return out


def filter_rows(rows: list[dict], flt: str, query: str) -> list[dict]:
    q = query.strip().lower()
    out = [r for r in rows if q in r["domain"]]
    if flt == "pending":
        out = [r for r in out if r["pending"]]
    elif flt == "found":
        out = [r for r in out if r["count"] > 0]
    elif flt == "agg":
        out = [r for r in out if r["aggregator"]]
    elif flt == "community":
        out = [r for r in out if r["source_type"] == "community"]
    return out


def site_url(domain: str) -> str:
    """Адрес для кнопки «Открыть сайт»: https://домен[/путь] (ключ сообщества domain/path тоже годится)."""
    d = (domain or "").strip().strip("/")
    return d if d.startswith(("http://", "https://")) else f"https://{d}"


def _row_label(r: dict) -> str:
    mark = "🟡" if r["pending"] else ("🔴" if r["status"] == "deny" else "🟢")
    tail = " 🔁" if r["aggregator"] else ""
    return f"{mark} {r['domain']}{tail} · 📄{r.get('materials', 0)} · 🔎{r['count']}"



def _render_detail(domain: str, registry: dict, row: dict) -> None:
    entry = registry.get(domain, {})
    pending = row["pending"]
    head = f"### {domain}"
    if pending:
        head += "  :orange[не проверен]"
    if row["aggregator"]:
        head += "  :violet[агрегатор]"
    st.markdown(head)
    st.link_button("Открыть сайт ↗", site_url(domain))
    mat = row.get("mat")
    st.caption(f"Материалов в GAR: {row.get('materials', 0)} · Находок поиска: {row['count']}")
    if mat:
        st.dataframe([{
            "Тип": _TYPE_LABELS.get(t, t), "Всего": v["published"] + v["dropped"],
            "Опубликовано": v["published"], "Отброшено": v["dropped"],
        } for t, v in mat["types"].items()], hide_index=True, width="stretch")
        if mat["dropped"]:
            st.caption("Отброшены из-за разрешения источника — задайте «Разрешение на публикацию» ниже.")
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
        help=f"Доступно: {{title}}, {{source_url}}, {{domain}}. Пример: {_ATTR_EXAMPLE}",
        key=f"attr_{domain}",
    )
    site_name = st.text_input(
        "Название сайта (срезается с конца title)",
        value=entry.get("site_name") or "",
        help="Например: Православный журнал «Фома». Пусто — title не меняется.",
        key=f"site_{domain}",
    )
    notes = st.text_area("Заметки", value=entry.get("notes", ""), key=f"notes_{domain}")
    source_type = st.selectbox(
        "Тип источника", _SOURCE_TYPES,
        index=_SOURCE_TYPES.index(row["source_type"]) if row["source_type"] in _SOURCE_TYPES else 0,
        format_func=_SOURCE_TYPE_LABELS.get, key=f"stype_{domain}",
    )
    c_author, c_city = st.columns(2)
    author = c_author.text_input("Автор", value=entry.get("author") or "", key=f"author_{domain}",
                                 help="Пусто — строка «Автор | Город» не выводится.")
    city = c_city.text_input("Город", value=entry.get("city") or "", key=f"city_{domain}")
    is_aggregator = st.checkbox(
        "Агрегатор", value=bool(entry.get("is_aggregator", False)), key=f"agg_{domain}",
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Сохранить", key=f"save_{domain}", type="primary", disabled=status is None, width="stretch"):
        registry[domain] = {
            "status": status,
            "attribution_template": attribution or default_attribution_template(domain),
            "site_name": site_name.strip(),
            "notes": notes,
            "checked_date": entry.get("checked_date"),
            "is_aggregator": is_aggregator,
            "publish_permission": permission,
            "source_type": source_type,
            "author": author.strip(),
            "city": city.strip(),
        }
        save_entry(domain, registry[domain])
        st.rerun()
    if c2.button("Отменить", key=f"cancel_{domain}", width="stretch"):
        for p in ("status", "perm", "attr", "site", "notes", "agg", "stype", "author", "city"):
            st.session_state.pop(f"{p}_{domain}", None)
        st.rerun()
    if c3.button("Удалить", key=f"del_{domain}", width="stretch"):
        try:
            _dismiss_domain(domain)
        except Exception as exc:  # noqa: BLE001
            notify.report("error", "Не удалось убрать находки домена в GAR", details=[str(exc)])
            return
        registry.pop(domain, None)
        delete_entry(domain)
        st.session_state.pop("dom_sel", None)
        st.rerun()


def render() -> None:
    st.header("Источники / домены")
    st.caption("Реестр ToS-статусов — источники в GAR (issue #3, ADR-0021). "
               "Новые домены попадают сюда автоматически со статусом «не проверен».")
    registry = _load_registry()
    rows = build_rows(registry, _domain_counts(), runner.load_source_stats())
    by_domain = {r["domain"]: r for r in rows}

    flt = st.radio(
        "Фильтр", list(_FILTERS), horizontal=True, label_visibility="collapsed",
        format_func=lambda k: f"{_FILTERS[k]} · {len(filter_rows(rows, k, ''))}",
    )
    left, right = st.columns([1, 1.4], gap="large")
    with left:
        query = st.text_input("Поиск", placeholder="домен, например unicef.org", label_visibility="collapsed", key="src_search")
        shown = filter_rows(rows, flt, query)
        size = st.selectbox("На странице", _PAGE_SIZES, index=0)
        pages = max(1, -(-len(shown) // size))
        page = st.number_input("Страница", 1, pages, 1) if pages > 1 else 1
        chunk = shown[(page - 1) * size: page * size]
        sel = st.session_state.get("dom_sel")
        if sel not in by_domain and rows:
            sel = st.session_state["dom_sel"] = (chunk or rows)[0]["domain"]
        for r in chunk:
            cb, cl = st.columns([8, 1], vertical_alignment="center")
            if cb.button(_row_label(r), key=f"pick_{r['domain']}", width="stretch",
                         type="primary" if r["domain"] == sel else "secondary"):
                st.session_state["dom_sel"] = r["domain"]
                st.rerun()
            cl.link_button("↗", site_url(r["domain"]), help="Открыть сайт источника")
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
            save_entry(nd, registry[nd])
            st.session_state["dom_sel"] = nd
            st.rerun()

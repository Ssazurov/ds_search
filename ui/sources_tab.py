"""Источники/домены — CRUD config/licenses.yaml + агрегация discovered_sources
по домену (issue #20 п.4, ADR-002: "это config/licenses.yaml, не новая таблица")."""
from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path

import streamlit as st
import yaml

from src.discovery.config import load_settings
from src.discovery.gar_client import GarDiscoveryClient
from src.license.checker import LicenseStatus, _CONFIG_PATH, normalize_domain

_STATUSES = [s.value for s in LicenseStatus if s != LicenseStatus.PENDING_MANUAL_REVIEW]


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
    return Counter(normalize_domain(r["domain"]) for r in rows if r.get("domain"))


def render() -> None:
    st.header("Источники / домены")
    st.caption("Реестр ToS-статусов — config/licenses.yaml (issue #3). "
               "pending_manual_review проставляется автоматически для новых доменов.")
    registry = _load_registry()
    counts = _domain_counts()

    for domain in sorted(set(registry) | set(counts)):
        entry = registry.get(domain, {})
        pending = entry.get("status") not in _STATUSES
        label = f"{domain} — находок: {counts.get(domain, 0)}"
        if pending:
            label += " · ⏳ не проверен"
        if entry.get("is_aggregator"):
            label += " · 🔁 агрегатор"
        with st.expander(label, expanded=pending):
            if pending:
                st.warning("Статус ещё не выбран — по умолчанию домен не скачивается (pending_manual_review).")
            status = st.selectbox(
                "Статус", _STATUSES,
                index=_STATUSES.index(entry.get("status")) if not pending else None,
                placeholder="— выбрать —",
                key=f"status_{domain}",
            )
            attribution = st.text_input(
                "Шаблон атрибуции ({title}, {source_url})",
                value=entry.get("attribution_template", ""), key=f"attr_{domain}",
            )
            notes = st.text_area("Заметки", value=entry.get("notes", ""), key=f"notes_{domain}")
            is_aggregator = st.checkbox(
                "Агрегатор (ссылка на первоисточник в конце текста статьи, ADR-0012)",
                value=bool(entry.get("is_aggregator", False)), key=f"agg_{domain}",
            )
            if st.button("Сохранить", key=f"save_{domain}", disabled=status is None):
                registry[domain] = {
                    "status": status,
                    "attribution_template": attribution or None,
                    "notes": notes,
                    "checked_date": entry.get("checked_date"),
                    "is_aggregator": is_aggregator,
                }
                _save_registry(registry)
                st.success("licenses.yaml обновлён")
                st.rerun()
            if st.button("Удалить домен из реестра", key=f"del_{domain}"):
                registry.pop(domain, None)
                _save_registry(registry)
                st.rerun()

    st.divider()
    st.subheader("Добавить домен")
    new_domain = st.text_input("Домен (например, example.org)")
    if st.button("Добавить", disabled=not new_domain.strip()):
        registry[new_domain.strip()] = {"status": "pending_manual_review", "notes": "", "attribution_template": None}
        _save_registry(registry)
        st.rerun()

    st.divider()
    st.subheader("Добавить новость по ссылке")
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
            "llm_failed": ("error", "LLM не смог собрать черновик по этому тексту"),
        }.get(result, ("error", result))
        getattr(st, level)(msg)

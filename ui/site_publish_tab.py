"""Вкладка «Внешний сайт»: кнопка пересборки ds_site на GitHub Pages (ds_search#225, ADR-0018)."""
from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

from src.license.registry_store import GarRegistryStore
from src.license.checker import PUBLISH_PERMISSION_LABELS, PublishPermission
from src.site_publish import runner
from src.site_publish.permissions import PUBLISHABLE, set_publish_permission
from src.tz import fmt_msk
from ui import notify

SITE_URL = "https://ssazurov.github.io/ds_site/"


def _counters(counts: list[dict]) -> None:
    rows = [{
        "Раздел": c["name"],
        "Опубликовано": c["published"],
        "Не выбрано (not_set)": c["skipped"].get("not_set", 0),
        "Запрещено (denied)": c["skipped"].get("denied", 0),
    } for c in counts]
    a, b, c_ = st.columns(3)
    a.metric("Опубликовано", sum(r["Опубликовано"] for r in rows))
    b.metric("Отфильтровано: не выбрано", sum(r["Не выбрано (not_set)"] for r in rows))
    c_.metric("Отфильтровано: запрещено", sum(r["Запрещено (denied)"] for r in rows))
    st.dataframe(rows, use_container_width=True, hide_index=True)


_PERMS = [p.value for p in PublishPermission]
_MAX_EDIT_ROWS = 30


def _open_source(domain: str) -> None:
    GarRegistryStore().ensure(domain)  # нет в реестре -> заготовка, иначе во вкладке «Источники» домена не будет
    st.session_state["dom_sel"] = domain
    st.session_state["active_tab"] = "Источники"


def _dropped() -> None:
    rows = runner.load_dropped()
    if not rows:
        return
    saved = st.session_state.setdefault("dp_saved", {})
    st.subheader("Отброшено по источникам")
    st.caption("Правка пишет в реестр источников; в сайт попадёт после следующей пересборки.")
    def _txt(r: dict) -> str:
        return f"{r['domain'] or '(нет домена)'} · {r['count']} материалов · {', '.join(r['types'])} · {r['permission']}"

    text_w = max(len(_txt(r)) for r in rows[:_MAX_EDIT_ROWS])
    for r in rows[:_MAX_EDIT_ROWS]:
        dom, n = r["domain"], r["count"]
        cur = saved.get(dom, r["permission"])
        row = st.container(key=f"cmp_dp_{dom or 'none'}")
        c0, c1, c2, c3 = row.columns(4)
        c0.markdown(
            f'<div style="width:{text_w}ch;max-width:60vw"><b>{html.escape(r["domain"] or "(нет домена)")}</b> · {n} материалов · '
            f'{html.escape(", ".join(r["types"]))} · <code>{html.escape(r["permission"])}</code></div>',
            unsafe_allow_html=True)
        if not dom:
            continue
        new = c1.selectbox(
            "Разрешение", _PERMS, index=_PERMS.index(cur) if cur in _PERMS else 0,
            format_func=lambda v: PUBLISH_PERMISSION_LABELS[PublishPermission(v)],
            key=f"dp_sel_{dom}", label_visibility="collapsed", width=240,
        )
        if new != cur and new in PUBLISHABLE:
            c0.caption(f"+{n} материалов после пересборки")
        if c2.button("Сохранить", key=f"dp_save_{dom}", disabled=new == cur):
            try:
                set_publish_permission(dom, new)
            except Exception as exc:  # noqa: BLE001 - показать пользователю
                notify.report("error", f"Не удалось сохранить {dom}", details=[str(exc)])
            else:
                saved[dom] = new
                st.rerun()
        c3.button("В источник", key=f"dp_open_{dom}", on_click=_open_source, args=(dom,))
    if len(rows) > _MAX_EDIT_ROWS:
        st.caption(f"Показаны первые {_MAX_EDIT_ROWS} из {len(rows)} источников; остальные — во вкладке «Источники».")


def render() -> None:
    st.caption(
        f"{SITE_URL} · выгрузка из GAR → фильтр по разрешению источника → сборка → "
        "публикация. Публикуются только «Разрешение не требуется» и «Разрешение получено» "
        "(поле задаётся во вкладке «Источники»). Предыдущая версия сайта перезаписывается."
    )

    st_ = runner.status()
    dry = st.checkbox("Пробный прогон (собрать и проверить, без публикации)", key="site_dry")
    confirm = st.checkbox(
        "Подтверждаю пересборку и публикацию (предыдущая версия сайта будет перезаписана)",
        key="site_confirm", disabled=dry,
    )
    err = runner.check_env(dry)
    if err:
        notify.report("error", "Ошибка окружения", details=[err])
    if st.button("Пересобрать внешний сайт", type="primary",
                 disabled=bool(err) or st_.running or not (dry or confirm)):
        try:
            runner.start(dry_run=dry)
        except RuntimeError as exc:
            notify.report("error", "Не удалось запустить пересборку", details=[str(exc)])
        else:
            notify.report("success", "Публикация на внешний сайт запущена",
                         stats={"тип": "пробный прогон" if dry else "публикация",
                                "старт": fmt_msk(datetime.fromtimestamp(runner.status().started_at or 0, tz=timezone.utc))})
            st.rerun()
    if st.button("Обновить статус"):
        st.rerun()

    if st_.started_at is None:
        st.info("Пересборка ещё не запускалась.")
        return
    when = fmt_msk(datetime.fromtimestamp(st_.started_at, tz=timezone.utc))
    kind = "пробный прогон" if st_.dry_run else "публикация"
    if st_.running:
        st.warning(f"Идёт {kind} (старт {when}) — нажмите «Обновить статус».")
    elif st_.exit_code == 0:
        st.success(f"Готово: {kind}, старт {when}." + (f" [{st_.url}]({st_.url})" if st_.url else ""))
    else:
        st.error(f"{kind.capitalize()} завершилась с ошибкой (код {st_.exit_code}, старт {when}). См. лог.")
    if st_.counts:
        _counters(st_.counts)
    _dropped()
    with st.expander("Лог", expanded=bool(st_.running or st_.exit_code)):
        st.code(st_.log or "(пусто)", language="text")

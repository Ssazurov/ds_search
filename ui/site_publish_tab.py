"""Вкладка «Внешний сайт»: кнопка пересборки ds_site на GitHub Pages (ds_search#225, ADR-0018)."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.license.registry_store import GarRegistryStore
from src.license.checker import PUBLISH_PERMISSION_LABELS, PublishPermission
from src.site_publish import runner
from src.site_publish.permissions import PUBLISHABLE, set_publish_permission
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
    for r in rows[:_MAX_EDIT_ROWS]:
        dom, n = r["domain"], r["count"]
        cur = saved.get(dom, r["permission"])
        c0, c1, c2, c3 = st.columns([3, 3, 1.3, 1.7])
        c0.markdown(f"**{dom or '(нет домена)'}** · {n} материалов · {', '.join(r['types'])} · `{r['permission']}`")
        if not dom:
            continue
        new = c1.selectbox(
            "Разрешение", _PERMS, index=_PERMS.index(cur) if cur in _PERMS else 0,
            format_func=lambda v: PUBLISH_PERMISSION_LABELS[PublishPermission(v)],
            key=f"dp_sel_{dom}", label_visibility="collapsed",
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
        c3.button("В Источники", key=f"dp_open_{dom}", on_click=_open_source, args=(dom,))
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
                                "старт": datetime.fromtimestamp(runner.status().started_at or 0).strftime("%Y-%m-%d %H:%M:%S")})
            st.rerun()
    if st.button("Обновить статус"):
        st.rerun()

    if st_.started_at is None:
        st.info("Пересборка ещё не запускалась.")
        return
    when = datetime.fromtimestamp(st_.started_at).strftime("%Y-%m-%d %H:%M:%S")
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

"""Вкладка «Внешний сайт»: кнопка пересборки ds_site на GitHub Pages (ds_search#225, ADR-0018)."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.site_publish import runner

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


def render() -> None:
    st.header("Внешний сайт (GitHub Pages)")
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
        st.error(err)
    if st.button("Пересобрать внешний сайт", type="primary",
                 disabled=bool(err) or st_.running or not (dry or confirm)):
        try:
            runner.start(dry_run=dry)
        except RuntimeError as exc:
            st.error(str(exc))
        else:
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
    with st.expander("Лог", expanded=bool(st_.running or st_.exit_code)):
        st.code(st_.log or "(пусто)", language="text")

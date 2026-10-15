"""Вкладка «Пересборка» (ds_search#744): кнопки пересборки сайтов/приложения; вторая подвкладка — «Админка на GitHub»."""
from __future__ import annotations

import streamlit as st

from src.site_publish import runner
from ui import notify, persist, site_publish_tab
from ui.stories_tab import _sg

# (кнопка, служебный id статуса, режим publish_story.sh, ссылка)
_JOBS = [
    ("Пересобрать локальный сайт", "_site", "site", "http://localhost:3001"),
    ("Пересобрать приложение (локально)", "_app", "app", "http://localhost:8081/"),
    ("Пересобрать политику и приложение на GitHub", "_gh", "gh", "https://ssazurov.github.io/ds_app_site/"),
]


@st.fragment(run_every=5)
def _status(sg, sid: str) -> None:
    ps = sg.publish_status(sid)
    if ps:
        st.caption(("❌ " if "ошибка" in ps else "✅ " if "готово" in ps else "⏳ ") + ps)


def _site_gh() -> None:
    st_ = runner.status()
    err = runner.check_env(False)
    c = st.columns([3, 5], vertical_alignment="center")
    if c[0].button("Пересобрать сайт на GitHub", key="rb_ghsite", type="primary",
                   disabled=bool(err) or st_.running, use_container_width=True):
        try:
            runner.start(dry_run=False)
        except RuntimeError as exc:
            notify.report("error", "Не удалось запустить пересборку", details=[str(exc)])
        else:
            st.rerun()
    c[1].markdown(f"[{site_publish_tab.SITE_URL}]({site_publish_tab.SITE_URL})")
    if err:
        c[1].caption(err)
    elif st_.running:
        c[1].caption("⏳ идёт публикация — подробности во вкладке «Админка на GitHub»")
    elif st_.started_at is not None:
        c[1].caption("✅ готово" if st_.exit_code == 0 else f"❌ ошибка (код {st_.exit_code})")


def _jobs() -> None:
    sg = _sg()
    for label, sid, mode, url in _JOBS:
        c = st.columns([3, 5], vertical_alignment="center")
        if c[0].button(label, key=f"rb_{sid}", type="primary", use_container_width=True):
            sg.request_publish(sid, mode)
        c[1].markdown(f"[{url}]({url})")
        with c[1]:
            _status(sg, sid)
    _site_gh()
    st.caption("Нужен воркер publish_watch.sh (запущен как ds-publish-watch.service).")


def render() -> None:
    t1, t2 = persist.tabs(["Сайты и приложение", "Админка на GitHub"], "rb_main")
    with t1:
        _jobs()
    with t2:
        site_publish_tab.render()

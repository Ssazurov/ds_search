"""Вкладка «Пересборка» (ds_search#744): кнопки пересборки сайтов/приложения; вторая подвкладка — «Админка на GitHub»."""
from __future__ import annotations

import streamlit as st

from src.site_publish import runner
from ui import notify, persist, site_publish_tab
from ui.stories_tab import _sg

_NB = "\u00a0"  # пустая подпись: у всех строк одинаковая высота и отступы

# (кнопка, служебный id статуса, режим publish_story.sh, ссылка)
_JOBS = [
    ("Пересобрать админку (локально)", "_admin", "admin", "http://localhost:8501/"),
    ("Пересобрать локальный сайт", "_site", "site", "http://localhost:3001"),
    None,  # «Пересобрать сайт на GitHub» (_site_gh)
    ("Пересобрать приложение (локально)", "_app", "app", "http://localhost:8081/"),
    ("Пересобрать APK", "_apk", "apk", ""),
    ("Пересобрать политику и приложение на GitHub", "_gh", "gh", "https://ssazurov.github.io/ds_app_site/"),
]


@st.fragment(run_every=5)
def _status(sg, sid: str, url: str) -> None:
    ps = sg.publish_status(sid)
    st.markdown(f"[{url}]({url})" if url else _NB)
    st.caption((("❌ " if "ошибка" in ps else "✅ " if "готово" in ps else "⏳ ") + ps) if ps else _NB)


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
    if err:
        note = err
    elif st_.running:
        note = "⏳ идёт публикация — подробности во вкладке «Админка на GitHub»"
    elif st_.started_at is not None:
        note = "✅ готово" if st_.exit_code == 0 else f"❌ ошибка (код {st_.exit_code})"
    else:
        note = _NB
    with c[1]:
        st.markdown(f"[{site_publish_tab.SITE_URL}]({site_publish_tab.SITE_URL})")
        st.caption(note)


def _jobs() -> None:
    sg = _sg()
    st.markdown(
        "<style>.st-key-rb_rows [data-testid=stHorizontalBlock]{height:56px;gap:1rem;align-items:center}"
        ".st-key-rb_rows [data-testid=stColumn]{height:56px;overflow:hidden;display:flex;flex-direction:column;justify-content:center}"
        ".st-key-rb_rows [data-testid=stColumn]>[data-testid=stVerticalBlock]{gap:0}"
        ".st-key-rb_rows [data-testid=stCaptionContainer]{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".st-key-rb_rows{gap:.5rem}</style>", unsafe_allow_html=True)
    box = st.container(key="rb_rows")
    with box:
        for job in _JOBS:
            if job is None:
                _site_gh()
                continue
            label, sid, mode, url = job
            c = st.columns([3, 5], vertical_alignment="center")
            if c[0].button(label, key=f"rb_{sid}", type="primary", use_container_width=True):
                sg.request_publish(sid, mode)
            with c[1]:
                _status(sg, sid, url)
            if sid == "_apk":
                st.columns([3, 5], vertical_alignment="center")[0].text_input(
                    "Код активации", "197911", key="actcode", help="Код активации приложения после установки")
    st.caption("Нужен воркер publish_watch.sh (запущен как ds-publish-watch.service).")


def render() -> None:
    t1, t2 = persist.tabs(["Сайты и приложение", "Админка на GitHub"], "rb_main")
    with t1:
        _jobs()
    with t2:
        site_publish_tab.render()
    site_publish_tab.render_log()

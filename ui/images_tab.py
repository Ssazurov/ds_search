"""Страница «Картинки» (ds_search#695): свободная генерация изображений с историей запусков.
Ядро — ds_words/scripts/storygen.py (g*-функции). Оформление и ключи контейнеров те же, что на странице «Истории» (ui/theme.py, _STORIES)."""
from __future__ import annotations

import time

import streamlit as st

from ui import notify
from ui import rowtable
from ui.rowtable import ROW_H, VISIBLE
from ui.stories_tab import _sg


def _when(r, fmt="%d.%m %H:%M"):
    return time.strftime(fmt, time.localtime(r["created"]))


def _fmt(r):
    p = (r["prompt"] or "—").replace("\n", " ")
    t = r.get("title")
    return f"{t + ' · ' if t else ''}{_when(r)} · {p[:60]}{'…' if len(p) > 60 else ''} · {len(r['variants'])} шт."


def _table(sg, runs, cur):
    """Таблица запусков: клик по названию открывает запись, 🗑 — в последней ячейке строки."""
    w = [6, 2, 1, 1, 1, 1]
    with st.container(key="stimgtab"):
        for c, t in zip(st.columns(w), ["Название", "Время", "Шт.", "♥", "Папка", ""]):
            if t:
                c.markdown(f"**{t}**")
        with st.container(height=VISIBLE * ROW_H if len(runs) > VISIBLE else "content", border=False, key="stimgtab_rows"):
            for r in runs:
                c = st.columns(w, vertical_alignment="center")
                p = (r["prompt"] or "").replace("\n", " ")
                on = r["id"] == cur
                if c[0].button((r.get("title") or p[:40] or "—"), key=f"imgopen_{r['id']}",
                               use_container_width=True, type="secondary" if on else "tertiary"):
                    st.session_state["img_sel"] = r["id"]; st.rerun()
                c[1].markdown(_when(r, "%d.%m.%Y %H:%M"))
                c[2].markdown(str(len(r["variants"])))
                c[3].markdown(str(sum(1 for v in r["variants"] if v.get("liked"))))
                vs = r["variants"]
                f = next((v["file"] for v in vs if v["id"] == r["selected"]), vs[0]["file"] if vs else "")
                if c[4].button("📂", key=f"imgdir_{r['id']}", help="Показать картинку в проводнике Windows", disabled=not vs):
                    d = sg.gwork().parent / "open"; d.mkdir(parents=True, exist_ok=True)
                    (d / f"{r['id']}.req").write_text(f); st.toast("Открываю проводник…")
                if c[5].button("🗑", key=f"imgdel_{r['id']}", help="Удалить запись"):
                    _del_run(sg, r["id"], r.get("title") or p)


def _gallery(sg, rid, run):
    vs, sel, key = run["variants"], run["selected"], f"img_{rid}_"
    for j in range(0, len(vs), 4):
        for c, v in zip(st.columns(4), vs[j:j + 4]):
            c.image(str(sg.gwork() / v["file"]),
                    caption=f"{rowtable.var_name(vs, v['id'])} · {v['id']} · seed {v['seed']}" + (" · ✅" if v["id"] == sel else "") + (" · ♥" if v.get("liked") else "")
                    + (f" · из {v['parent']}" if v.get("parent") else ""))
            rowtable.img_buttons(c, key, v["id"], f"strf_img_{rid}", lambda: sg.gselect(rid, v["id"]),
                                 lambda: sg.glike(rid, v["id"], not v.get("liked")), lambda: sg.gdelete(rid, v["id"]))


@st.dialog("Удалить запуск?")
def _del_run(sg, rid, prompt):
    st.write(f"Удалить запуск «{prompt[:80]}» вместе с картинками?")
    c = st.columns(2)
    if c[0].button("Удалить", type="primary", key=f"imgdelok_{rid}"):
        sg.gdelete_run(rid)
        if st.session_state.get("img_sel") == rid:
            st.session_state["img_sel"] = "new"
        st.rerun()
    if c[1].button("Отмена", key=f"imgdelno_{rid}"):
        st.rerun()


def _render():
    sg, ss = _sg(), st.session_state
    if "img_goto" in ss:
        ss["img_sel"] = ss.pop("img_goto")
    runs = sorted(sg.gload()["runs"], key=lambda r: r["created"], reverse=True)
    by = {r["id"]: r for r in runs}
    if "img_sel" not in ss:
        ss["img_sel"] = st.query_params.get("img", "new")
    if ss["img_sel"] not in by:
        ss["img_sel"] = "new"
    rid = ss["img_sel"]
    st.query_params["img"] = rid
    with st.container(key="sthead_top"):
        top = st.columns([1, 4], vertical_alignment="center")
    if top[0].button("＋ Новый запуск", key="img_new", type="primary" if rid == "new" else "secondary"):
        ss["img_sel"] = "new"; st.rerun()
    if runs:
        _table(sg, runs, rid)
    run = by.get(rid)
    key = f"img_{rid}_"
    with st.container(key=f"stp_img_{rid}"):
        title = st.text_input("Название", run.get("title", "") if run else "", key=key + "t")
        if run and title.strip() != run.get("title", ""):
            sg.gset_title(rid, title.strip()); st.rerun()
        prompt = st.text_area("Промпт", run["prompt"] if run else "", height=110, key=key + "p",
                              placeholder="Что нарисовать (по-русски или по-английски)")
    with st.form(key=f"fm_stgen_img_{rid}", border=False):
        with st.container(key=f"stgen_img_{rid}"):
            g = st.columns(4)
    n = g[0].number_input("Кол-во", 1, sg.GMAX, 5, key="img_n")
    extra = g[1].text_input("Доп. промпт (по-русски)", key=key + "ex")
    if g[2].form_submit_button("Сгенерировать"):
        if not prompt.strip():
            st.warning("Введите промпт"); return
        r_id = rid if run else sg.gnew(prompt.strip())
        if not run and title.strip():
            sg.gset_title(r_id, title.strip())
        with notify.busy(f"Генерация {int(n)} изобр. (~6 с/шт)…"):
            try:
                sg.ggen(r_id, int(n), prompt.strip(), extra=extra.strip())
            except Exception as e:  # ComfyUI/Ollama недоступны, ошибка workflow
                if not run and not next(r for r in sg.gload()["runs"] if r["id"] == r_id)["variants"]:
                    sg.gdelete_run(r_id)
                st.error(f"Ошибка генерации: {e}"); return
        st.session_state["img_goto"] = r_id; st.rerun()
    if g[3].form_submit_button("Удалить без ♥", help="Выбранные и лайкнутые остаются"):
        st.toast(f"Удалено: {sg.gprune(rid) if run else 0}"); st.rerun()
    if not run:
        return
    _gallery(sg, rid, run)
    vids = [v["id"] for v in run["variants"]]
    if vids:
        with st.form(key=f"fm_strf_img_{rid}", border=False):
            with st.container(key=f"strf_img_{rid}"):
                r = st.columns(3)
        par = r[0].selectbox("Доработать", vids, index=vids.index(run["selected"]) if run["selected"] in vids else 0, key=key + "par", format_func=rowtable.var_fmt(run["variants"]))
        ex = r[1].text_input("Что изменить (по-русски)", key=key + "rex", placeholder="сделай фон светлее")
        if r[2].form_submit_button("Доработать") and ex.strip():
            with notify.busy("Доработка…"):
                try:
                    sg.ggen(rid, 2, parent=par, extra=ex.strip())
                except Exception as e:
                    st.error(f"Ошибка генерации: {e}"); return
            st.rerun()
    if runs:
        with st.container(key="stfoot"):
            a = st.columns(2)
        if a[0].button("Удалить без ♥ (вся история)", key="img_prall"):
            st.toast(f"Удалено: {sg.gprune()}"); st.rerun()


def render():
    _render()
    rowtable.scroll_pending()

"""Вкладка «Истории» (ds_search#614): тексты шагов → кадры (ComfyUI, FLUX.2 klein) → выбор/доработка → принятие.
Ядро — ds_words/scripts/storygen.py (DS_WORDS_DIR, COMFY_URL). Вкладка читает/пишет файлы ds_words."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import streamlit as st
import yaml


def _sg():
    root = os.environ.get("DS_WORDS_DIR") or str(Path(__file__).resolve().parents[2] / "ds_words")
    os.environ.setdefault("DS_WORDS_DIR", root)
    p = str(Path(root) / "scripts")
    if p not in sys.path:
        sys.path.insert(0, p)
    import storygen
    return storygen


def _save_story(sg, sid, story):
    (sg.ROOT / f"stories/{sid}.yaml").write_text(
        yaml.safe_dump(story, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")


def _status(stt):
    if stt["accepted"]:
        return "принята"
    return "в работе" if any(x["variants"] for x in stt["steps"].values()) else "черновик"


def _list(sg, ids):
    rows = []
    for i in ids:
        s, stt = sg.load_story(i), sg.load_state(i)
        rows.append({"id": i, "название": s["title"]["ru"], "категория": s.get("category", ""), "уровень": s.get("level", ""),
                     "герой": stt["hero"], "статус": _status(stt), "шагов": len(s["steps"]),
                     "с картинкой": sum(1 for x in stt["steps"].values() if x["selected"])})
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _create(sg, ch):
    with st.expander("Создать историю"):
        c = st.columns(4)
        sid = c[0].text_input("id (слаг)", key="ns_id")
        title = c[1].text_input("Название", key="ns_title")
        cat = c[2].text_input("Категория", "routine", key="ns_cat")
        loc = c[3].selectbox("Локация 1-го шага", list(ch["locations"]), key="ns_loc")
        if st.button("Создать", key="ns_go"):
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", sid or "") or (sg.ROOT / f"stories/{sid}.yaml").exists():
                st.error("id: латиница/цифры/_, уникальный")
            elif not title.strip():
                st.error("Нужно название")
            else:
                _save_story(sg, sid, {"id": sid, "category": cat, "level": 1, "tags": [], "title": {"ru": title.strip()},
                                      "steps": [{"id": "s1", "text": {"ru": ""}, "hero": True, "characters": ["hero"],
                                                 "outfit": "home", "location": loc}]})
                st.rerun()


def _gallery(sg, sid, k, state, key):
    stp = state["steps"][k]
    vs, sel = stp["variants"], stp["selected"]
    for j in range(0, len(vs), 4):
        for c, v in zip(st.columns(4), vs[j:j + 4]):
            c.image(str(sg.work(sid) / v["file"]),
                    caption=f"{v['id']} · seed {v['seed']}" + (" · ✅" if v["id"] == sel else "") + (" · ♥" if v.get("liked") else ""))
            b = c.columns(3)
            if b[0].button("✔", key=f"{key}s{v['id']}", help="Выбрать"):
                sg.select(sid, k, v["id"]); st.rerun()
            if b[1].button("♥", key=f"{key}l{v['id']}", help="Лайк"):
                sg.like(sid, k, v["id"], not v.get("liked")); st.rerun()
            if b[2].button("🗑", key=f"{key}d{v['id']}", help="Удалить"):
                sg.delete(sid, k, v["id"]); st.rerun()


def _step(sg, sid, story, state, ch, idx, s):
    k, key = s["id"], f"{sid}_{s['id']}_"
    stp = state["steps"][k]
    locs, outs = list(ch["locations"]), list(ch["characters"]["hero"]["outfits"])
    with st.container(border=True):
        h = st.columns([6, 1, 1, 1])
        h[0].markdown(f"**{k}**")
        move = (-1 if h[1].button("⬆", key=key + "up", disabled=idx == 0) else 0) or (1 if h[2].button("⬇", key=key + "dn", disabled=idx == len(story["steps"]) - 1) else 0)
        drop = h[3].button("✖", key=key + "rm", help="Удалить шаг", disabled=len(story["steps"]) < 2)
        c = st.columns([4, 1, 1])
        text = c[0].text_area("Текст (ru)", s["text"].get("ru", ""), key=key + "t", height=70)
        loc = c[1].selectbox("Локация", locs, index=locs.index(s["location"]) if s["location"] in locs else 0, key=key + "loc")
        outfit = c[2].selectbox("Одежда", outs, index=outs.index(s.get("outfit", "home")) if s.get("outfit", "home") in outs else 0, key=key + "out")
        action = st.text_input("Действие кадра (EN, фрагмент промпта)", stp["action"], key=key + "a")
        note = st.text_input("Заметка автора", stp["note"], key=key + "n")
        if st.button("Сохранить шаг", key=key + "sv"):
            s["text"]["ru"], s["location"], s["outfit"] = text, loc, outfit
            _save_story(sg, sid, story); sg.set_step(sid, k, action=action, note=note); st.rerun()
        if move or drop:
            sts = story["steps"]
            if drop:
                sts.pop(idx)
            else:
                sts[idx], sts[idx + move] = sts[idx + move], sts[idx]
            _save_story(sg, sid, story); st.rerun()
        with st.expander("Итоговый промпт"):
            st.code(sg.build_prompt(ch, {**s, "text": {"ru": text}, "location": loc, "outfit": outfit}, action, state["hero"]), language=None)
        g = st.columns([1, 3, 1, 1])
        n = g[0].number_input("N", 1, 6, 3, key=key + "n3")
        extra = g[1].text_input("Доп. промпт", key=key + "ex")
        if g[2].button("Сгенерировать", key=key + "gen"):
            with st.spinner(f"Генерация {n} кадр. (~6 с/кадр)…"):
                try:
                    sg.set_step(sid, k, action=action, note=note)
                    sg.gen(sid, k, int(n), extra)
                except Exception as e:  # ComfyUI недоступен / ошибка workflow
                    st.error(f"Ошибка генерации: {e}"); return
            st.rerun()
        if g[3].button("Удалить без ♥", key=key + "pr", help="Выбранные и лайкнутые остаются"):
            st.toast(f"Удалено: {sg.prune(sid, k)}"); st.rerun()
        _gallery(sg, sid, k, state, key)
        if stp["variants"]:
            r = st.columns([1, 3, 1])
            par = r[0].selectbox("Доработать", [v["id"] for v in stp["variants"]], key=key + "par")
            ex = r[1].text_input("Что изменить (EN)", key=key + "rex", placeholder="remove the towel from the wall")
            if r[2].button("Доработать", key=key + "ref", disabled=not ex.strip()):
                with st.spinner("Доработка…"):
                    try:
                        sg.gen(sid, k, 2, ex.strip(), parent=par)
                    except Exception as e:
                        st.error(f"Ошибка генерации: {e}"); return
                st.rerun()


def render():
    sg = _sg()
    if not (sg.ROOT / "stories").is_dir():
        st.error(f"Нет каталога историй: {sg.ROOT}/stories. Задайте DS_WORDS_DIR."); return
    ids = sorted(p.stem for p in (sg.ROOT / "stories").glob("*.yaml") if p.stem != "categories")
    ch = sg.registry()
    if ids:
        _list(sg, ids)
    _create(sg, ch)
    if not ids:
        return
    sid = st.selectbox("История", ids, key="stories_sel")
    story, state = sg.load_story(sid), sg.load_state(sid)
    top = st.columns([1, 2, 1])
    hero = top[0].radio("Герой", ["girl", "boy"], index=["girl", "boy"].index(state["hero"]), horizontal=True, key=f"hero_{sid}")
    if hero != state["hero"]:
        state["hero"] = hero; sg.save_state(sid, state); st.rerun()
    title = top[1].text_input("Название", story["title"]["ru"], key=f"ttl_{sid}")
    if title != story["title"]["ru"] and title.strip():
        story["title"]["ru"] = title.strip(); _save_story(sg, sid, story)
    for idx, s in enumerate(story["steps"]):
        _step(sg, sid, story, state, ch, idx, s)
    if st.button("+ шаг", key=f"add_{sid}"):
        n = 1 + max(int(re.sub(r"\D", "", x["id"]) or 0) for x in story["steps"])
        last = story["steps"][-1]
        story["steps"].append({"id": f"s{n}", "text": {"ru": ""}, "hero": True, "characters": ["hero"],
                               "outfit": last.get("outfit", "home"), "location": last["location"]})
        _save_story(sg, sid, story); st.rerun()
    st.divider()
    a = st.columns(2)
    if a[0].button("Удалить без ♥ (вся история)", key=f"prall_{sid}"):
        st.toast(f"Удалено: {sg.prune(sid)}"); st.rerun()
    if a[1].button("Принять историю", type="primary", key=f"acc_{sid}"):
        ok, log = sg.accept(sid)
        (st.success if ok else st.error)(log[-1500:])

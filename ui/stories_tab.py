"""Вкладка «Истории» (ds_search#614): тексты шагов → кадры (ComfyUI, FLUX.2 klein) → выбор/доработка → принятие.
Ядро — ds_words/scripts/storygen.py (DS_WORDS_DIR, COMFY_URL). Вкладка читает/пишет файлы ds_words."""
from __future__ import annotations

import io
import os
import re
import sys
import textwrap
from pathlib import Path

import streamlit as st
import yaml


def _sg():
    """storygen из каталога историй: DS_STORIES_DIR (ds_words на main), иначе DS_WORDS_DIR."""
    root = os.environ.get("DS_STORIES_DIR") or os.environ.get("DS_WORDS_DIR") or str(Path(__file__).resolve().parents[2] / "ds_words")
    p = str(Path(root) / "scripts")
    if p not in sys.path:
        sys.path.insert(0, p)
    os.environ.setdefault("DS_WORDS_DIR", root)
    import storygen
    storygen.ROOT = Path(root)
    return storygen


def _enter(flag):
    """Enter в однострочном поле = нажатие связанной кнопки (флаг в session_state)."""
    return {"on_change": st.session_state.__setitem__, "args": (flag, True)}


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
        with st.container(key="scmeta_new"):
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


def _font(size):
    from PIL import ImageFont
    for f in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    try:
        import matplotlib
        return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"), size)
    except Exception:
        return ImageFont.load_default()


def _strip(sg, sid, story, state) -> bytes:
    """Ряд: колонка на шаг (подпись + выбранный и лайкнутые варианты друг под другом)."""
    from PIL import Image, ImageDraw
    T, H = 320, 90
    cols = []
    for s in story["steps"]:
        stp = state["steps"][s["id"]]
        vs = [v for v in stp["variants"] if v["id"] == stp["selected"] or v.get("liked")]
        cols.append((s, sorted(vs, key=lambda v: v["id"] != stp["selected"]), stp["selected"]))
    rows = max(1, max(len(v) for _, v, _ in cols))
    im = Image.new("RGB", (len(cols) * T, H + rows * T), "white")
    d, f, fb = ImageDraw.Draw(im), _font(14), _font(18)
    for i, (s, vs, sel) in enumerate(cols):
        x = i * T
        d.text((x + 6, 4), s["id"], fill="black", font=fb)
        for n, line in enumerate(textwrap.wrap(s["text"].get("ru", ""), 34)[:4]):
            d.text((x + 6, 28 + n * 16), line, fill=(60, 60, 60), font=f)
        if not vs:
            d.text((x + 6, H + 6), "нет выбранной / ♥", fill=(180, 0, 0), font=f)
        for j, v in enumerate(vs):
            y = H + j * T
            im.paste(Image.open(sg.work(sid) / v["file"]).convert("RGB").resize((T - 6, T - 6)), (x + 3, y + 3))
            d.rectangle((x + 1, y + 1, x + T - 2, y + T - 2), outline=(0, 160, 0) if v["id"] == sel else (220, 60, 120), width=3)
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def _step(sg, sid, story, state, ch, idx, s):
    k, key = s["id"], f"{sid}_{s['id']}_"
    stp = state["steps"][k]
    locs, outs = list(ch["locations"]), list(ch["characters"]["hero"]["outfits"])
    with st.container(border=True, key=f"stp_{sid}_{k}"):
        st.markdown(f"**{idx + 1}. {s['text'].get('ru', '') or '— текст не задан (вкладка «Сценарий») —'}**")
        text = s["text"].get("ru", "")
        scs, sit = sg.lib("scenes"), sg.lib("items")
        sopt = [""] + list(scs)
        scn = st.selectbox("Сцена", sopt, index=sopt.index(s["scene"]) if s.get("scene") in scs else 0, key=key + "scn",
                           format_func=lambda x: scs[x]["title"]["ru"] if x else "— локация реестра —")
        uses = []
        if scn:
            ids = [it["item"] for it in scs[scn].get("items", [])]
            uses = st.multiselect("Используемые предметы (на сцене не рисуются)", ids, default=[u for u in s.get("uses", []) if u in ids],
                                  format_func=lambda x: sit.get(x, {}).get("title", {}).get("ru", x), key=key + "us")
            if len(uses) > 1:
                st.caption("Фон — состояние «без предмета» только для первого из выбранных; остальные исключены из описания сцены.")
            loc = s["location"]
        else:
            loc = st.selectbox("Локация", locs, index=locs.index(s["location"]) if s["location"] in locs else 0, key=key + "loc")
        outfit = st.selectbox("Одежда", outs, index=outs.index(s.get("outfit", "home")) if s.get("outfit", "home") in outs else 0, key=key + "out")
        action = st.text_input("Действие кадра", stp["action"], key=key + "a", help="По-русски; в модель уйдёт по-английски", **_enter(key + "svgo"))
        note = st.text_input("Заметка автора", stp["note"], key=key + "n", **_enter(key + "svgo"))
        if st.button("Сохранить шаг", key=key + "sv") | st.session_state.pop(key + "svgo", False):
            s["text"]["ru"], s["location"], s["outfit"] = text, loc, outfit
            for kk, vv in (("scene", scn), ("uses", uses)):
                s.pop(kk, None)
                if vv: s[kk] = vv
            _save_story(sg, sid, story); sg.set_step(sid, k, action=action, note=note); st.rerun()
        if st.checkbox("Показать итоговый промпт (английский, уходит в модель)", key=key + "pv"):
            try:
                pr = sg.build_prompt(ch, {**s, "text": {"ru": text}, "location": loc, "outfit": outfit, "scene": scn, "uses": uses}, action, state["hero"],
                                     extra=st.session_state.get(key + "ex", ""))
                st.session_state[key + "pt"] = pr
                st.text_area("Промпт (англ.)", height=max(110, 24 * (len(pr) // 110 + 2)), key=key + "pt", disabled=True)
            except Exception as e:  # Ollama недоступна и т.п.
                st.warning(str(e))
        with st.form(key="fm_" + f"stgen_{sid}_{k}", border=False):
            with st.container(key=f"stgen_{sid}_{k}"):
                g = st.columns(4)
        n = g[0].number_input("Кол-во", 1, 8, 5, key=key + "n3")
        extra = g[1].text_input("Доп. промпт (по-русски)", key=key + "ex")
        if g[2].form_submit_button("Сгенерировать"):
            with st.spinner(f"Генерация {n} кадр. (~6 с/кадр)…"):
                try:
                    sg.set_step(sid, k, action=action, note=note)
                    sg.gen(sid, k, int(n), extra)
                except Exception as e:  # ComfyUI недоступен / ошибка workflow
                    st.error(f"Ошибка генерации: {e}"); return
            st.rerun()
        if g[3].form_submit_button("Удалить без ♥", help="Выбранные и лайкнутые остаются"):
            st.toast(f"Удалено: {sg.prune(sid, k)}"); st.rerun()
        _gallery(sg, sid, k, state, key)
        if stp["variants"]:
            with st.form(key="fm_" + f"strf_{sid}_{k}", border=False):
                with st.container(key=f"strf_{sid}_{k}"):
                    r = st.columns(3)
            par = r[0].selectbox("Доработать", [v["id"] for v in stp["variants"]], key=key + "par")
            ex = r[1].text_input("Что изменить (по-русски)", key=key + "rex", placeholder="убери полотенце со стены")
            go = r[2].form_submit_button("Доработать")
            if go and ex.strip():
                with st.spinner("Доработка…"):
                    try:
                        sg.gen(sid, k, 2, ex.strip(), parent=par)
                    except Exception as e:
                        st.error(f"Ошибка генерации: {e}"); return
                st.rerun()


def _new_step(story, text=""):
    n = 1 + max([int(re.sub(r"\D", "", x["id"]) or 0) for x in story["steps"]] or [0])
    last = story["steps"][-1] if story["steps"] else {"outfit": "home", "location": "bathroom"}
    story["steps"].append({"id": f"s{n}", "text": {"ru": text}, "hero": True, "characters": ["hero"],
                           "outfit": last.get("outfit", "home"), "location": last["location"]})


def _scenario(sg, sid, story, state):
    """Предварительный этап: тексты шагов, порядок, категория/уровень/теги."""
    with st.container(key=f"scmeta_{sid}"):
        c = st.columns([2, 1, 3])
    cat = c[0].text_input("Категория", story.get("category", ""), key=f"cat_{sid}")
    lvl = c[1].number_input("Уровень", 1, 9, int(story.get("level", 1)), key=f"lvl_{sid}")
    tags = [t.strip() for t in c[2].text_input("Теги (через запятую)", ", ".join(story.get("tags", [])), key=f"tg_{sid}").split(",") if t.strip()]
    if (cat, lvl, tags) != (story.get("category", ""), int(story.get("level", 1)), story.get("tags", [])):
        story.update(category=cat, level=int(lvl), tags=tags); _save_story(sg, sid, story)
    steps, changed = story["steps"], False
    for idx, s in enumerate(steps):
        k = s["id"]; has = bool(state["steps"][k]["variants"])
        with st.container(key=f"scrow_{sid}_{k}"):
            r = st.columns(5)
        r[0].markdown(f"**{idx + 1}**")
        t = r[1].text_area("Текст шага", s["text"].get("ru", ""), key=f"sc_{sid}_{k}", height=68, label_visibility="collapsed")
        if t != s["text"].get("ru", ""):
            s["text"]["ru"] = t; changed = True
        move = (-1 if r[2].button("⬆", key=f"scu_{sid}_{k}", disabled=idx == 0) else 0) or (1 if r[3].button("⬇", key=f"scd_{sid}_{k}", disabled=idx == len(steps) - 1) else 0)
        drop = r[4].button("✖", key=f"scx_{sid}_{k}", disabled=has or len(steps) < 2, help="Удалить шаг" if not has else "У шага есть кадры — сначала удалите их во вкладке «Кадры»")
        if move or drop:
            if drop:
                steps.pop(idx)
            else:
                steps[idx], steps[idx + move] = steps[idx + move], steps[idx]
            _save_story(sg, sid, story); st.rerun()
    if changed:
        _save_story(sg, sid, story)
    if st.button("+ шаг", key=f"add_{sid}"):
        _new_step(story); _save_story(sg, sid, story); st.rerun()
    with st.expander("Добавить шаги списком (по строке на шаг)"):
        with st.container(key="scmeta_bulk"):
            bulk = st.text_area("Шаги", key=f"bulk_{sid}", height=120, placeholder="Я подхожу к ванной.\nВключаю свет.")
        if st.button("Добавить", key=f"bulkgo_{sid}"):
            for line in [x.strip() for x in bulk.splitlines() if x.strip()]:
                _new_step(story, line)
            _save_story(sg, sid, story); st.rerun()


def _ru(old, new):
    """Поле {ru, en?}: если ru не менялся — как было (ручной en сохраняется), иначе новый ru без en."""
    return old if isinstance(old, dict) and old.get("ru", "") == new else {"ru": new}


def _sgallery(sg, scn, stt, key, kind=None, op=None):
    vs, sel = stt["variants"], stt["selected"]
    for j in range(0, len(vs), 4):
        for c, v in zip(st.columns(4), vs[j:j + 4]):
            c.image(str(sg.swork(scn) / v["file"]),
                    caption=f"{v['id']} · seed {v['seed']}" + (" · ✅" if v["id"] == sel else "") + (" · ♥" if v.get("liked") else ""))
            b = c.columns(3)
            if b[0].button("✔", key=f"{key}s{v['id']}", help="Выбрать"):
                sg.sselect(scn, v["id"], kind); op and st.session_state.__setitem__(op, True); st.rerun()
            if b[1].button("♥", key=f"{key}l{v['id']}", help="Лайк"):
                sg.slike(scn, v["id"], not v.get("liked"), kind); op and st.session_state.__setitem__(op, True); st.rerun()
            if b[2].button("🗑", key=f"{key}d{v['id']}", help="Удалить"):
                sg.sdelete(scn, v["id"], kind); op and st.session_state.__setitem__(op, True); st.rerun()


def _scenes_list(sg, scenes):
    rows = []
    for k, sc in scenes.items():
        stt = sg.sload(k)
        rows.append({"id": k, "название": sc["title"]["ru"], "предметов": len(sc.get("items", [])), "видов": len(stt["variants"]),
                     "выбран": "да" if stt["selected"] else "нет"})
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _scenes(sg):
    """Вкладка «Сцены» (ds_search#621): статика помещения + камера, предметы с размещением, виды (5), выбор/♥/доработка."""
    scenes, items = sg.lib("scenes"), sg.lib("items")
    if scenes:
        _scenes_list(sg, scenes)
    with st.expander("Создать сцену"):
        with st.container(key="scmeta_nsc"):
            c = st.columns(2)
        nid = c[0].text_input("id (слаг)", key="nsc_id")
        nt = c[1].text_input("Название", key="nsc_title")
        if st.button("Создать", key="nsc_go"):
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", nid or "") or nid in scenes:
                st.error("id: латиница/цифры/_, уникальный")
            elif not nt.strip():
                st.error("Нужно название")
            else:
                scenes[nid] = {"title": {"ru": nt.strip()}, "desc": {"ru": ""}, "camera": {"ru": ""}, "items": []}
                sg.lib_save("scenes", scenes); st.rerun()
    if not scenes:
        return
    with st.container(key="sthead_top_sn"):
        top = st.columns(3)
    scn = top[0].selectbox("Сцена", list(scenes), format_func=lambda k: scenes[k]["title"]["ru"], key="scn_sel")
    sc = scenes[scn]; k = f"sn_{scn}_"
    title = top[1].text_input("Название", sc["title"].get("ru", ""), key=k + "t")
    if title != sc["title"].get("ru", "") and title.strip():
        sc["title"] = {"ru": title.strip()}; sg.lib_save("scenes", scenes)
    stt = sg.sload(scn)
    with st.container(border=True, key=f"stp_{scn}"):
        desc = st.text_area("Описание помещения (статика)", sc["desc"].get("ru", ""), key=k + "d", height=100)
        cam = st.text_input("Камера / раскладка", sc.get("camera", {}).get("ru", ""), key=k + "c",
                            placeholder="вид спереди, камера на уровне груди ребёнка", **_enter(k + "svgo"))
        places = []
        for i, it in enumerate(sc["items"]):
            with st.container(key=f"snrow_{scn}_{i}"):
                r = st.columns(3)
            r[0].markdown(items.get(it["item"], {}).get("title", {}).get("ru", it["item"]))
            places.append(r[1].text_input("Размещение", it.get("place", {}).get("ru", ""), key=f"{k}pl{i}",
                                          label_visibility="collapsed", **_enter(k + "svgo")))
            if r[2].button("✖", key=f"{k}rm{i}", help="Убрать из сцены"):
                sc["items"].pop(i); sg.lib_save("scenes", scenes); st.rerun()
        if st.button("Сохранить сцену", key=k + "sv") | st.session_state.pop(k + "svgo", False):
            sc["desc"], sc["camera"] = _ru(sc["desc"], desc), _ru(sc.get("camera"), cam)
            for it, p in zip(sc["items"], places):
                it["place"] = _ru(it.get("place"), p)
            sg.lib_save("scenes", scenes); st.toast("Сохранено"); st.rerun()
        with st.expander("Добавить предмет"):
            free = [x for x in items if x not in {it["item"] for it in sc["items"]}]
            with st.container(key=f"stgen_add_{scn}"):
                a = st.columns(4)
            pick = a[0].selectbox("Предмет", free, format_func=lambda x: items[x]["title"]["ru"], key=k + "np", disabled=not free)
            pl = a[1].text_input("Размещение", key=k + "npl", placeholder="висит на крючке справа от раковины")
            if (a[2].button("Добавить", key=k + "add")) and pick and pl.strip():
                sc["items"].append({"item": pick, "place": {"ru": pl.strip()}}); sg.lib_save("scenes", scenes); st.rerun()
            with st.container(key=f"scmeta_ni_{scn}"):
                n = st.columns(3)
            iid = n[0].text_input("Новый предмет: id", key=k + "ni")
            it_t = n[1].text_input("Название", key=k + "nit")
            it_d = n[2].text_input("Описание", key=k + "nid")
            if st.button("Создать предмет", key=k + "newgo_b"):
                if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", iid or "") or iid in items or not it_t.strip():
                    st.error("id: латиница/цифры/_, уникальный; нужно название")
                else:
                    items[iid] = {"title": {"ru": it_t.strip()}, "desc": {"ru": it_d.strip()}}; sg.lib_save("items", items); st.rerun()
        if st.checkbox("Показать итоговый промпт (английский, уходит в модель)", key=k + "pv"):
            try:
                pr = sg.scene_prompt(scn, st.session_state.get(k + "ex", ""))
                st.session_state[k + "pt"] = pr
                st.text_area("Промпт (англ.)", height=max(110, 24 * (len(pr) // 110 + 2)), key=k + "pt", disabled=True)
            except Exception as e:
                st.warning(str(e))
        with st.form(key="fm_" + f"stgen_{scn}", border=False):
            with st.container(key=f"stgen_{scn}"):
                g = st.columns(4)
        n = g[0].number_input("Кол-во", 1, 8, 5, key=k + "n")
        extra = g[1].text_input("Доп. промпт (по-русски)", key=k + "ex")
        if g[2].form_submit_button("Сгенерировать"):
            with st.spinner(f"Генерация {n} видов (~6 с/вид)…"):
                try:
                    sg.sgen(scn, int(n), extra)
                except Exception as e:
                    st.error(f"Ошибка генерации: {e}"); return
            st.rerun()
        if g[3].form_submit_button("Удалить без ♥", help="Выбранный и лайкнутые остаются"):
            st.toast(f"Удалено: {sg.sprune(scn)}"); st.rerun()
        _sgallery(sg, scn, stt, k)
        if stt["variants"]:
            with st.form(key="fm_" + f"strf_{scn}", border=False):
                with st.container(key=f"strf_{scn}"):
                    r = st.columns(3)
            par = r[0].selectbox("Доработать", [v["id"] for v in stt["variants"]], key=k + "par")
            ex = r[1].text_input("Что изменить (по-русски)", key=k + "rex", placeholder="убери полотенце со стены")
            go = r[2].form_submit_button("Доработать")
            if go and ex.strip():
                with st.spinner("Доработка…"):
                    try:
                        sg.sgen(scn, 2, ex.strip(), parent=par)
                    except Exception as e:
                        st.error(f"Ошибка генерации: {e}"); return
                st.rerun()
        _sstates(sg, scn, stt, items, sc, k)


def _sstates(sg, scn, stt, items, sc, k):
    """Состояния сцены (ds_search#623): «без предмета X» — правка выбранного вида «все предметы»."""
    kinds = sg.sstates(scn)
    if not kinds:
        return
    st.markdown("##### Состояния сцены")
    if not stt["selected"]:
        st.caption("Выберите вид «все предметы» (✔) — состояния строятся его правкой.")
        return
    with st.container(key=f"stgen_all_{scn}"):
        a = st.columns(3)
    n = a[0].number_input("Кол-во на состояние", 1, 8, 2, key=k + "sn")
    if a[1].button("Сгенерировать все", key=k + "sall", help="Для состояний без выбранного вида"):
        with st.spinner("Генерация состояний…"):
            try:
                c = sg.sgen_all(scn, int(n))
            except Exception as e:
                st.error(f"Ошибка генерации: {e}"); return
        st.toast(f"Сгенерировано: {c}"); st.rerun()
    for kd in kinds:
        iid = kd.split(":", 1)[1]
        sk = stt.get("states", {}).get(kd, {"selected": None, "variants": []})
        kk = f"{k}{kd}_"
        ttl = items.get(iid, {}).get("title", {}).get("ru", iid)
        with st.expander(f"Без: {ttl} — видов {len(sk['variants'])}" + (" ✅" if sk["selected"] else ""), expanded=bool(st.session_state.get(kk + "op"))):
            with st.form(key="fm_" + f"stgen_{scn}_{kd}", border=False):
                with st.container(key=f"stgen_{scn}_{kd}"):
                    g = st.columns(4)
            m = g[0].number_input("Кол-во", 1, 8, 5, key=kk + "n")
            ex = g[1].text_input("Доп. промпт (по-русски)", key=kk + "ex")
            if g[2].form_submit_button("Сгенерировать"):
                with st.spinner(f"Генерация {m} видов…"):
                    try:
                        sg.sgen(scn, int(m), ex, kind=kd)
                    except Exception as e:
                        st.error(f"Ошибка генерации: {e}"); return
                st.session_state[kk + "op"] = True; st.rerun()
            if g[3].form_submit_button("Удалить без ♥"):
                st.session_state[kk + "op"] = True; st.toast(f"Удалено: {sg.sprune(scn, kd)}"); st.rerun()
            _sgallery(sg, scn, sk, kk, kd, kk + "op")
            if sk["variants"]:
                with st.form(key="fm_" + f"strf_{scn}_{kd}", border=False):
                    with st.container(key=f"strf_{scn}_{kd}"):
                        r = st.columns(3)
                par = r[0].selectbox("Доработать", [v["id"] for v in sk["variants"]], key=kk + "par")
                rx = r[1].text_input("Что изменить (по-русски)", key=kk + "rex")
                go = r[2].form_submit_button("Доработать")
                if go and rx.strip():
                    with st.spinner("Доработка…"):
                        try:
                            sg.sgen(scn, 2, rx.strip(), parent=par, kind=kd)
                        except Exception as e:
                            st.error(f"Ошибка генерации: {e}"); return
                    st.session_state[kk + "op"] = True; st.rerun()


def _igallery(sg, iid, kind, stt, key):
    vs, sel = stt[kind]["variants"], stt[kind]["selected"]
    for j in range(0, len(vs), 4):
        for c, v in zip(st.columns(4), vs[j:j + 4]):
            c.image(str(sg.iwork(iid) / v["file"]),
                    caption=f"{v['id']} · seed {v['seed']}" + (" · ✅" if v["id"] == sel else "") + (" · ♥" if v.get("liked") else ""))
            b = c.columns(3)
            if b[0].button("✔", key=f"{key}s{v['id']}", help="Выбрать"):
                sg.iselect(iid, kind, v["id"]); st.rerun()
            if b[1].button("♥", key=f"{key}l{v['id']}", help="Лайк"):
                sg.ilike(iid, kind, v["id"], not v.get("liked")); st.rerun()
            if b[2].button("🗑", key=f"{key}d{v['id']}", help="Удалить"):
                sg.idelete(iid, kind, v["id"]); st.rerun()


def _ikind(sg, iid, kind, title, stt):
    ks = kind.replace(":", "_")
    k = f"it_{iid}_{ks}_"
    stt.setdefault(kind, {"selected": None, "variants": []})
    if title: st.markdown(f"**{title}**")
    if st.checkbox("Показать итоговый промпт (английский, уходит в модель)", key=k + "pv"):
        try:
            pr = sg.item_prompt(iid, kind, st.session_state.get(k + "ex", ""))
            st.session_state[k + "pt"] = pr
            st.text_area("Промпт (англ.)", height=max(110, 24 * (len(pr) // 110 + 2)), key=k + "pt", disabled=True)
        except Exception as e:
            st.warning(str(e))
    with st.form(key="fm_" + f"stgen_{iid}_{ks}", border=False):
        with st.container(key=f"stgen_{iid}_{ks}"):
            g = st.columns(4)
    n = g[0].number_input("Кол-во", 1, 8, 5, key=k + "n")
    extra = g[1].text_input("Доп. промпт (по-русски)", key=k + "ex")
    if g[2].form_submit_button("Сгенерировать"):
        with st.spinner(f"Генерация {n} (~6 с/кадр)…"):
            try:
                sg.igen(iid, kind, int(n), extra)
            except Exception as e:
                st.error(f"Ошибка генерации: {e}"); return
        st.rerun()
    if g[3].form_submit_button("Удалить без ♥", help="Выбранный и лайкнутые остаются"):
        st.toast(f"Удалено: {sg.iprune(iid, kind)}"); st.rerun()
    _igallery(sg, iid, kind, stt, k)
    if stt[kind]["variants"]:
        with st.form(key="fm_" + f"strf_{iid}_{ks}", border=False):
            with st.container(key=f"strf_{iid}_{ks}"):
                r = st.columns(3)
        par = r[0].selectbox("Доработать", [v["id"] for v in stt[kind]["variants"]], key=k + "par")
        ex = r[1].text_input("Что изменить (по-русски)", key=k + "rex", placeholder="сделай поменьше")
        go = r[2].form_submit_button("Доработать")
        if go and ex.strip():
            with st.spinner("Доработка…"):
                try:
                    sg.igen(iid, kind, 2, ex.strip(), parent=par)
                except Exception as e:
                    st.error(f"Ошибка генерации: {e}"); return
            st.rerun()


def _items(sg):
    """Вкладка «Предметы» (ds_search#622): описание, вид на нейтральном фоне и «в руках» (герой или любой персонаж), выбор/♥/доработка."""
    items, hold = sg.lib("items"), sg.holders()
    if items:
        rows = []
        for i, it in items.items():
            s = sg.iload(i)
            hands = [v for kk, x in s.items() if kk.startswith("hand:") for v in x["variants"]]
            rows.append({"id": i, "название": it["title"]["ru"], "видов": len(s["view"]["variants"]), "вид выбран": "да" if s["view"]["selected"] else "нет",
                         "в руках": len(hands)})
        st.dataframe(rows, hide_index=True, use_container_width=True)
    with st.expander("Создать предмет"):
        with st.container(key="scmeta_nit"):
            n = st.columns(3)
        iid = n[0].text_input("id (слаг)", key="nit_id")
        it_t = n[1].text_input("Название", key="nit_t")
        it_d = n[2].text_input("Описание", key="nit_d")
        if st.button("Создать", key="nit_go"):
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", iid or "") or iid in items or not it_t.strip():
                st.error("id: латиница/цифры/_, уникальный; нужно название")
            else:
                items[iid] = {"title": {"ru": it_t.strip()}, "desc": {"ru": it_d.strip()}}; sg.lib_save("items", items); st.rerun()
    if not items:
        return
    with st.container(key="sthead_top_it"):
        top = st.columns(3)
    iid = top[0].selectbox("Предмет", list(items), format_func=lambda x: items[x]["title"]["ru"], key="itm_sel")
    it = items[iid]
    title = top[1].text_input("Название", it["title"].get("ru", ""), key=f"it_{iid}_t")
    if title != it["title"].get("ru", "") and title.strip():
        it["title"] = {"ru": title.strip()}; sg.lib_save("items", items)
    who = top[2].selectbox("Герой", ["all"] + list(hold), format_func=lambda x: "Все" if x == "all" else hold[x], key="it_hero")
    stt = sg.iload(iid)
    with st.container(border=True, key=f"stp_it_{iid}"):
        desc = st.text_area("Описание предмета", it["desc"].get("ru", ""), key=f"it_{iid}_d", height=100)
        if st.button("Сохранить", key=f"it_{iid}_sv"):
            it["desc"] = _ru(it["desc"], desc); sg.lib_save("items", items); st.toast("Сохранено"); st.rerun()
        _ikind(sg, iid, "view", "Вид (нейтральный фон)", stt)
        for h in (list(hold) if who == "all" else [who]):
            _ikind(sg, iid, f"hand:{h}", f"В руках — {hold[h]} (держит предмет)", stt)


def _chars(sg):
    """Вкладка «Персонажи» (ds_search#641): реестр characters.yaml — герой и остальные, одежда (общая и по варианту героя), референс-листы."""
    ch = sg.registry(); chs = ch["characters"]
    st.dataframe([{"id": i, "имя": sg.txt_ru(c.get("name")) or i, "тип": "герой" if "variants" in c else "персонаж",
                   "одежд": len(c.get("outfits") or {})} for i, c in chs.items()], hide_index=True, use_container_width=True)
    nloc = len([l for l in (ch.get("locations") or {}) if l not in sg.lib("scenes")])
    if nloc and st.button(f"Перенести локации реестра в сцены ({nloc})", key="chr_mig"):
        st.toast(f"Добавлено сцен: {sg.migrate_locations()}"); st.rerun()
    with st.expander("Создать персонажа"):
        with st.container(key="scmeta_nch"):
            n = st.columns(3)
        cid = n[0].text_input("id (слаг)", key="nch_id")
        nm = n[1].text_input("Имя", key="nch_n")
        bb = n[2].text_input("Внешность (англ.)", key="nch_b")
        if st.button("Создать", key="nch_go"):
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", cid or "") or cid in chs or not nm.strip() or not bb.strip():
                st.error("id: латиница/цифры/_, уникальный; нужны имя и внешность")
            else:
                chs[cid] = {"kind": "character", "name": {"ru": nm.strip()}, "bible": bb.strip(), "refs": [], "outfits": {}}
                sg.registry_save(ch); st.rerun()
    with st.container(key="sthead_top_ch"):
        top = st.columns(3)
    cid = top[0].selectbox("Персонаж", list(chs), format_func=lambda x: sg.txt_ru(chs[x].get("name")) or x, key="chr_sel")
    c = chs[cid]; hero = "variants" in c; vs = list(c.get("variants", {}))
    with st.container(border=True, key=f"stp_ch_{cid}"):
        nm = st.text_input("Имя", sg.txt_ru(c.get("name")), key=f"ch_{cid}_n")
        bibles = {v: st.text_area(f"Внешность (англ.) — {sg.holders(ch).get(v, v)}", c["variants"][v].get("bible", ""), key=f"ch_{cid}_b{v}", height=90)
                  for v in vs} if hero else {None: st.text_area("Внешность (англ.)", c.get("bible", ""), key=f"ch_{cid}_b", height=90)}
        if st.button("Сохранить", key=f"ch_{cid}_sv"):
            c["name"] = {"ru": nm.strip() or cid}
            for v, b in bibles.items():
                (c["variants"][v] if hero else c)["bible"] = b.strip()
            sg.registry_save(ch); st.toast("Сохранено"); st.rerun()
        outs = c.setdefault("outfits", {})
        st.markdown("**Одежда**")
        for oid, o in list(outs.items()):
            with st.expander(f"{sg.txt_ru(o.get('title')) or oid} · {oid}" + (f" · только {o['only']}" if o.get("only") else "")):
                t = st.text_input("Название", sg.txt_ru(o.get("title")), key=f"co_{cid}_{oid}_t")
                d = st.text_area("Описание (англ.)", o.get("desc", ""), key=f"co_{cid}_{oid}_d", height=80)
                byh = {v: st.text_input(f"Описание для варианта «{v}» (пусто = общее)", (o.get("by_hero") or {}).get(v, ""), key=f"co_{cid}_{oid}_h{v}")
                       for v in vs}
                only = st.selectbox("Герой", ["", *vs], format_func=lambda x: x or "все", key=f"cosel_{cid}_{oid}",
                                    index=(["", *vs].index(o["only"]) if o.get("only") in vs else 0)) if hero else ""
                b = st.columns(2)
                if b[0].button("Сохранить", key=f"co_{cid}_{oid}_sv"):
                    o["title"] = {"ru": t.strip() or oid}; o["desc"] = d.strip()
                    h = {v: x.strip() for v, x in byh.items() if x.strip()}
                    o.pop("by_hero", None); o.pop("only", None)
                    if h: o["by_hero"] = h
                    if only: o["only"] = only
                    sg.registry_save(ch); st.toast("Сохранено"); st.rerun()
                if b[1].button("Удалить одежду", key=f"co_{cid}_{oid}_del"):
                    del outs[oid]; sg.registry_save(ch); st.rerun()
        with st.expander("Добавить одежду"):
            with st.container(key=f"scmeta_nco_{cid}"):
                a = st.columns(3)
            oid = a[0].text_input("id (слаг)", key=f"nco_{cid}_id")
            ot = a[1].text_input("Название", key=f"nco_{cid}_t")
            od = a[2].text_input("Описание (англ.)", key=f"nco_{cid}_d")
            if st.button("Добавить", key=f"nco_{cid}_go"):
                if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", oid or "") or oid in outs or not ot.strip() or not od.strip():
                    st.error("id: латиница/цифры/_, уникальный; нужны название и описание")
                else:
                    outs[oid] = {"title": {"ru": ot.strip()}, "desc": od.strip()}; sg.registry_save(ch); st.rerun()
    iid = "chr_" + cid; stt = sg.iload(iid)
    kinds = {}
    for v in (vs or [None]):
        pre, who = (f"{{}}:{v}" if v else "{}"), (f" — {sg.holders(ch).get(v, v)}" if v else "")
        kinds[pre.format("sheet")] = f"Референс-лист{who}"
        for oid, o in outs.items():
            if v is None or not o.get("only") or o["only"] == v:
                kinds[f"outfit:{oid}:{v}" if v else f"outfit:{oid}"] = f"Одежда «{sg.txt_ru(o.get('title')) or oid}»{who}"
    with st.container(border=True, key=f"stp_chg_{cid}"):
        kind = st.selectbox("Вид (генерация)", list(kinds), format_func=kinds.get, key=f"ch_{cid}_kind")
        _ikind(sg, iid, kind, "", stt)


def _prompts(sg):
    """Вкладка «Промпты»: все шаблоны промптов генерации (умолчания — ds_words/library/prompts.default.yaml, правки — library/prompts.yaml)."""
    D = sg._defaults()
    st.caption("Английские шаблоны, уходящие в модель. Подстановки {имя} перечислены под полем. Пустое поле = умолчание. Правки хранятся в library/prompts.yaml.")
    G = [
        ("Общее (стиль, герой, местоимения)", ["style", "hero_who", "default_bible", "word_character", "pron_girl", "pron_boy", "pron_character", "outfit_part", "keep_item", "wearing_part"]),
        ("Шаги историй", ["hands_line", "step_loc", "step_scene"]),
        ("Локации и сцены", ["bg", "scene", "state_no"]),
        ("Предметы", ["item_view", "item_hand_ref", "item_hand"]),
        ("Персонажи", ["char_sheet", "char_new_outfit", "char_outfit_edit"]),
    ]
    used = {k for _, ks in G for k in ks}
    G.append(("Прочее", [k for k in D if k not in used]))
    new = {}
    for gt, ks in G:
        ks = [k for k in ks if k in D]
        if not ks:
            continue
        with st.expander(f"{gt} ({len(ks)})", expanded=(gt == G[0][0])):
            for k in ks:
                m = D[k]; cur = sg.P(k)
                new[k] = st.text_area(m["title"], cur, key=f"pr_{k}", height=max(68, 24 * (len(cur) // 90 + 2)))
                if m.get("vars"):
                    st.caption(f"Подстановки: {m['vars']}")
    b = st.columns(3)
    if b[0].button("Сохранить промпты", key="pr_save", type="primary"):
        sg.lib_save("prompts", {k: v.strip() for k, v in new.items() if v.strip() and v.strip() != D[k]["text"]})
        st.toast("Сохранено"); st.rerun()
    if b[1].button("Сбросить всё к умолчаниям", key="pr_reset"):
        sg.lib_save("prompts", {})
        for k in D:
            st.session_state.pop(f"pr_{k}", None)
        st.rerun()


def render():
    sg = _sg()
    t_st, t_sc, t_it, t_ch, t_pr = st.tabs(["Истории", "Сцены", "Предметы", "Персонажи", "Промпты"])
    with t_st:
        _stories(sg)
    with t_sc:
        _scenes(sg)
    with t_it:
        _items(sg)
    with t_ch:
        _chars(sg)
    with t_pr:
        _prompts(sg)


def _stories(sg):
    if not (sg.ROOT / "stories").is_dir():
        st.error(f"Нет каталога историй: {sg.ROOT}/stories. Задайте DS_WORDS_DIR."); return
    ids = sorted(p.stem for p in (sg.ROOT / "stories").glob("*.yaml") if p.stem != "categories")
    ch = sg.registry()
    if ids:
        _list(sg, ids)
    _create(sg, ch)
    if not ids:
        return
    with st.container(key="sthead_top"):
        top = st.columns(3)
    sid = top[0].selectbox("История", ids, key="stories_sel")
    story, state = sg.load_story(sid), sg.load_state(sid)
    hero = top[2].radio("Герой", ["girl", "boy"], index=["girl", "boy"].index(state["hero"]), horizontal=True, key=f"hero_{sid}")
    if hero != state["hero"]:
        state["hero"] = hero; sg.save_state(sid, state); st.rerun()
    title = top[1].text_input("Название", story["title"]["ru"], key=f"ttl_{sid}")
    if title != story["title"]["ru"] and title.strip():
        story["title"]["ru"] = title.strip(); _save_story(sg, sid, story)
    tab_sc, tab_fr, tab_vo = st.tabs(["Сценарий", "Кадры", "Озвучка"])
    with tab_sc:
        _scenario(sg, sid, story, state)
    with tab_fr:
        _frames(sg, sid, story, state, ch)
    with tab_vo:
        _voice(sg, sid, story)


def _voice(sg, sid, story):
    """Озвучка шагов (Chatterbox через tts_server): прослушивание, озвучить/перегенерировать. Файл: audio/ru/<история>_<шаг>.mp3."""
    from ui import words_tab as wt
    root, steps = sg.ROOT, story["steps"]
    path = lambda k: root / "audio" / "ru" / f"{sid}_{k}.mp3"
    with st.expander("Голос (профиль, референс, параметры)"):
        wt._tts_settings(root)

    def gen(ks):
        items = [{"id": f"{sid}_{x['id']}", "text": x["text"].get("ru", "").strip(), "stress": None}
                 for x in steps if x["id"] in ks and x["text"].get("ru", "").strip()]
        if not items:
            return 1, "Нет текста для озвучки"
        with st.spinner(f"Озвучка: {len(items)} шаг. (~несколько с на шаг)…"):
            return wt.run_tts(items)

    a = st.columns(3)
    todo = [x["id"] for x in steps if not path(x["id"]).is_file()]
    if a[0].button(f"Озвучить недостающие ({len(todo)})", key=f"vo_miss_{sid}", disabled=not todo):
        st.toast(gen(todo)[1]); st.rerun()
    if a[1].button("Перегенерировать все", key=f"vo_all_{sid}"):
        st.toast(gen([x["id"] for x in steps])[1]); st.rerun()
    for idx, x in enumerate(steps):
        k, f = x["id"], path(x["id"])
        with st.container(border=True, key=f"vo_{sid}_{k}"):
            c = st.columns([5, 4, 2])
            c[0].markdown(f"**{idx + 1}.** {x['text'].get('ru', '') or '— текст не задан —'}")
            if f.is_file():
                c[1].audio(f.read_bytes(), format="audio/mp3")
            else:
                c[1].caption("нет озвучки")
            if c[2].button("Заново" if f.is_file() else "Озвучить", key=f"vo_b_{sid}_{k}"):
                st.toast(gen([k])[1]); st.rerun()


def _frames(sg, sid, story, state, ch):
    for idx, s in enumerate(story["steps"]):
        _step(sg, sid, story, state, ch, idx, s)
    with st.container(key="stfoot"):
        a = st.columns(3)
    if a[2].button("Сгенерировать ряд", key=f"strip_{sid}", help="Общая картинка из выбранных и ♥ кадров всех шагов"):
        st.session_state[f"strip_img_{sid}"] = _strip(sg, sid, story, state)
    img = st.session_state.get(f"strip_img_{sid}")
    if img:
        st.image(img, caption="Ряд: зелёная рамка — выбранный, розовая — ♥")
        st.download_button("Скачать ряд (PNG)", img, f"{sid}_strip.png", "image/png", key=f"dl_{sid}")
    if a[0].button("Удалить без ♥ (вся история)", key=f"prall_{sid}"):
        st.toast(f"Удалено: {sg.prune(sid)}"); st.rerun()
    if a[1].button("Принять историю", type="primary", key=f"acc_{sid}"):
        ok, log = sg.accept(sid)
        (st.success if ok else st.error)(log[-1500:])

"""Слова — ревью и правка словаря (ds_words#6). Данные — YAML репозитория ds_words,
путь в env DS_WORDS_DIR (по умолчанию ../ds_words рядом с репозиторием ds). Вкладка только читает/пишет файлы.

Ревью работает как черновик (review/ui_decisions.json): вердикты ✓/✗ и правки ru/en/pos/переводов копятся
отдельно и попадают в YAML кнопкой «Применить». Формат решений совместим с `scripts/review.py apply`."""
from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import streamlit as st
import yaml

from ui import notify

POS = ["n", "v", "adj", "adv", "pron", "prep", "interj"]
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]+)?$")
MODES = {
    "all": "все", "flagged": "спорные", "unreviewed": "без ревью", "dups": "дубли",
    "no_tr": "нет перевода", "no_img": "нет картинки", "no_audio": "нет озвучки",
}
MANUAL = "manual.yaml"

CAT_RU = {
    "actions": "Действия", "animals": "Животные", "body": "Тело", "clothes": "Одежда",
    "colors": "Цвета", "core_verbs": "Основные глаголы", "descriptors": "Признаки",
    "dishes": "Блюда", "family": "Семья", "feelings": "Чувства", "food": "Еда",
    "furniture": "Мебель", "health": "Здоровье", "health_routines": "Гигиена и режим",
    "household": "Быт", "numbers_shapes": "Числа и формы", "outside": "На улице",
    "people": "Люди", "places": "Места", "prepositions_quantity": "Предлоги и количество",
    "pronouns_questions": "Местоимения и вопросы", "school": "Школа", "social": "Общение",
    "sounds": "Звуки", "sport": "Спорт", "time": "Время", "toys_games": "Игрушки и игры",
    "transport": "Транспорт",
}
POS_RU = {"n": "сущ.", "v": "глагол", "adj": "прил.", "adv": "нареч.",
          "pron": "мест.", "prep": "предлог", "interj": "междометие"}
POS_FROM = {v: k for k, v in POS_RU.items()}
LANG_RU = {"ru": "Русский", "en": "Английский", "de": "Немецкий", "fr": "Французский",
           "es": "Испанский", "kk": "Казахский", "uk": "Украинский", "be": "Белорусский"}
REVIEW_RU = {"": "", "ok": "✓ ок", "del": "✗ удалить"}
REVIEW_FROM = {v: k for k, v in REVIEW_RU.items()}


def cat_label(c: str) -> str:
    return CAT_RU.get(c, c)


def lang_label(l: str) -> str:
    return LANG_RU.get(l, l)


def words_dir() -> Path:
    env = os.environ.get("DS_WORDS_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "ds_words"


# ---------- чтение ----------

def load_rows(root: Path) -> tuple[list[dict], list[str]]:
    """Строки справочника (флаги из scripts/review.py, медиа из scripts/words.py) и список языков."""
    p = str(root / "scripts")
    if p not in sys.path:
        sys.path.insert(0, p)
    W, R = importlib.import_module("words"), importlib.import_module("review")
    words, errs = W.load()
    if errs:
        raise ValueError("; ".join(errs[:5]))
    flags = {r["id"]: r["flags"] for r in R.data()}
    dec = load_decisions(root)
    rows = []
    for w in words:
        img, aud = W.media(w["id"])
        rows.append({"id": w["id"], "cat": w["category"], "pos": w["pos"], "prio": w["prio"],
                     "age": w["age"], "note": w.get("note") or "",
                     "tr": w["tr"], "flags": flags.get(w["id"], []), "img": bool(img),
                     "audio": sorted(aud), "review": dec.get(w["id"], {}).get("verdict", "")})
    return rows, langs_of(rows)


def langs_of(rows: list[dict], extra: list[str] | None = None) -> list[str]:
    ls = {l for r in rows for l in r["tr"]} | set(extra or []) | {"ru"}
    return ["ru"] + sorted(ls - {"ru"})


def filter_rows(rows: list[dict], mode: str, cat: str, q: str, langs: list[str]) -> list[dict]:
    q = q.strip().lower()
    out = []
    for r in rows:
        if cat and cat != "все" and r["cat"] != cat:
            continue
        if q and q not in r["id"].lower() and not any(q in v.lower() for v in r["tr"].values()):
            continue
        ok = {
            "all": True,
            "flagged": bool(r["flags"]),
            "unreviewed": not r["review"],
            "dups": any(f.startswith("дубль") for f in r["flags"]),
            "no_tr": any(l not in r["tr"] for l in langs),
            "no_img": not r["img"],
            "no_audio": any(l in r["tr"] and l not in r["audio"] for l in langs),
        }[mode]
        if ok:
            out.append(r)
    return out


# ---------- черновик решений ----------
# {id: {"verdict": "ok"|"del", "ru": .., "en": .., "pos": .., "tr": {lang: ..}}}

def clean_entry(e) -> dict:
    if isinstance(e, str):
        e = {"verdict": e}
    if not isinstance(e, dict):
        return {}
    out: dict = {}
    if e.get("verdict") in ("ok", "del"):
        out["verdict"] = e["verdict"]
    if e.get("pos") in POS:
        out["pos"] = e["pos"]
    for k in ("ru", "en"):
        if isinstance(e.get(k), str) and e[k].strip():
            out[k] = e[k].strip()
    tr = {k: v.strip() for k, v in (e.get("tr") or {}).items()
          if LANG_RE.match(str(k)) and isinstance(v, str) and v.strip()}
    if tr:
        out["tr"] = tr
    return out


def load_decisions(root: Path) -> dict[str, dict]:
    f = root / "review" / "ui_decisions.json"
    raw = json.loads(f.read_text("utf-8")) if f.exists() else {}
    dec = {i: clean_entry(v) for i, v in raw.items()}
    return {i: v for i, v in dec.items() if v}


def save_decisions(root: Path, dec: dict[str, dict]) -> None:
    f = root / "review" / "ui_decisions.json"
    f.parent.mkdir(exist_ok=True)
    dec = {i: v for i, v in dec.items() if v}
    f.write_bytes(decisions_json(dec).encode("utf-8"))


def decisions_json(dec: dict[str, dict]) -> str:
    return json.dumps(dec, ensure_ascii=False, indent=1, sort_keys=True)


def stage(dec: dict, wid: str, field: str, value: str, orig: str = "") -> dict:
    """Записать правку поля; значение пустое или равное исходному — правка снимается."""
    e = dec.setdefault(wid, {})
    box = e if field in ("verdict", "pos", "ru", "en") else e.setdefault("tr", {})
    if value and value != orig:
        box[field] = value
    else:
        box.pop(field, None)
    if not e.get("tr"):
        e.pop("tr", None)
    if not e:
        dec.pop(wid, None)
    return dec


def toggle_verdict(dec: dict, wid: str, v: str) -> dict:
    cur = dec.get(wid, {}).get("verdict")
    return stage(dec, wid, "verdict", "" if cur == v else v)


def merge_decisions(dec: dict, incoming: dict) -> int:
    n = 0
    for wid, e in incoming.items():
        e = clean_entry(e)
        if not e or not ID_RE.match(str(wid)):
            continue
        cur = dec.setdefault(wid, {})
        tr = {**cur.get("tr", {}), **e.get("tr", {})}
        cur.update({k: v for k, v in e.items() if k != "tr"})
        if tr:
            cur["tr"] = tr
        n += 1
    return n


def counts(dec: dict[str, dict]) -> dict[str, int]:
    return {"ok": sum(e.get("verdict") == "ok" for e in dec.values()),
            "del": sum(e.get("verdict") == "del" for e in dec.values()),
            "edit": sum(any(k in e for k in ("ru", "en", "pos", "tr")) for e in dec.values())}


# ---------- запись (построчно, формат YAML сохраняется) ----------

def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _set_tr(line: str, lang: str, text: str) -> str:
    q = _q(text)
    if lang == "ru":
        return re.sub(r'ru: (?:"[^"]*"|[^,}]+?)(?=, pos:)', lambda m: "ru: " + q, line, count=1)
    m = re.search(r"tr: \{([^}]*)\}", line)
    if not m:
        return line.rstrip()[:-1] + f", tr: {{{lang}: {q}}}}}"
    body = m.group(1)
    if re.search(rf"(?:^|, ){re.escape(lang)}: ", body):
        body = re.sub(rf'(^|, ){re.escape(lang)}: (?:"[^"]*"|[^,}}]+)', lambda x: f"{x.group(1)}{lang}: {q}", body, count=1)
    else:
        body += f", {lang}: {q}"
    return line[:m.start()] + "tr: {" + body + "}" + line[m.end():]


def edit_word(root: Path, wid: str, *, tr: dict[str, str] | None = None,
              pos: str | None = None, delete: bool = False) -> bool:
    pat = re.compile(r'\{id: "?%s"?,' % re.escape(wid))
    found = False
    for f in sorted((root / "words").glob("*.yaml")):
        out, changed = [], False
        for ln in f.read_text("utf-8").split("\n"):
            if pat.search(ln):
                found = changed = True
                if delete:
                    continue
                for lang, t in (tr or {}).items():
                    ln = _set_tr(ln, lang, t)
                if pos:
                    ln = re.sub(r"pos: \w+", "pos: " + pos, ln, count=1)
            out.append(ln)
        if changed:
            f.write_bytes("\n".join(out).encode("utf-8"))
    return found


def add_word(root: Path, cat: str, wid: str, ru: str, pos: str, prio: int,
             tr: dict[str, str] | None = None, existing_ids: set[str] | None = None) -> None:
    if not ID_RE.match(wid):
        raise ValueError("id: латиница, цифры, _; начинается с буквы")
    if wid in (existing_ids or set()):
        raise ValueError(f"id {wid} уже есть")
    if not ru.strip() or pos not in POS or prio not in (1, 2, 3) or not cat.strip():
        raise ValueError("нужны категория, ru, pos, prio 1-3")
    f = root / "words" / MANUAL
    d = yaml.safe_load(f.read_text("utf-8")) if f.exists() else {"source": "manual-ui", "categories": {}}
    c = d["categories"].setdefault(cat.strip(), {"age": [2, 6], "words": []})
    w = {"id": wid, "ru": ru.strip(), "pos": pos}
    if prio != 2:
        w["prio"] = prio
    if tr:
        w["tr"] = {k: v.strip() for k, v in tr.items() if v.strip()}
    c["words"].append(w)
    f.write_bytes(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=10**6,
                                 default_flow_style=None).encode("utf-8"))


def apply_decisions(root: Path) -> dict[str, int]:
    """Применить черновик к YAML: ✗ — удалить слово, правки ru/en/pos/переводов — записать.
    Вердикты ✓ остаются в черновике, применённые правки и ✗ убираются."""
    dec, n, keep = load_decisions(root), {"del": 0, "edit": 0}, {}
    for wid, e in dec.items():
        if e.get("verdict") == "del":
            n["del"] += int(edit_word(root, wid, delete=True))
            continue
        tr = {k: e[k] for k in ("ru", "en") if k in e} | e.get("tr", {})
        if tr or e.get("pos"):
            n["edit"] += int(edit_word(root, wid, tr=tr, pos=e.get("pos")))
        if e.get("verdict"):
            keep[wid] = {"verdict": e["verdict"]}
    save_decisions(root, keep)
    return n


# ---------- команды ----------

def _run(root: Path, *cmd: str) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def run_validate(root: Path) -> tuple[int, str]:
    return _run(root, sys.executable, "scripts/words.py", "validate")


def run_export(root: Path) -> tuple[int, str]:
    return _run(root, sys.executable, "scripts/words.py", "export")


def commit(root: Path, branch: str, msg: str) -> tuple[int, str]:
    cur = _run(root, "git", "branch", "--show-current")[1]
    if branch and branch != cur:
        rc, out = _run(root, "git", "checkout", "-b", branch)
        if rc:
            rc, out = _run(root, "git", "checkout", branch)
        if rc:
            return rc, out
    paths = ["words"] + (["review/ui_decisions.json"] if (root / "review" / "ui_decisions.json").exists() else [])
    _run(root, "git", "add", *paths)
    return _run(root, "git", "commit", "-m", msg)


# ---------- UI ----------

def _bump(key: str) -> None:
    st.session_state[key] = st.session_state.get(key, 0) + 1


def _cb_stage(wid: str, field: str, key: str, orig: str) -> None:
    root = words_dir()
    dec = load_decisions(root)
    v = st.session_state.get(key, "")
    stage(dec, wid, field, v.strip() if isinstance(v, str) else v, orig)
    save_decisions(root, dec)


def _cb_toggle(wid: str, v: str) -> None:
    root = words_dir()
    dec = load_decisions(root)
    toggle_verdict(dec, wid, v)
    save_decisions(root, dec)


def _review(root: Path, rows: list[dict], langs: list[str]) -> None:
    dec = load_decisions(root)
    c = counts(dec)
    st.caption(f"✓ ок: {c['ok']} · ✗ удалить: {c['del']} · с правками: {c['edit']} · всего слов: {len(rows)}")

    f1, f2, f3, f4, f5 = st.columns([2, 3, 1.5, 1.5, 1.2])
    cats = ["все"] + sorted({r["cat"] for r in rows}, key=cat_label)
    cat = f1.selectbox("Категория", cats, key="rv_cat", format_func=lambda x: "Все" if x == "все" else cat_label(x))
    q = f2.text_input("Поиск (id или перевод)", key="rv_q")
    only_fl = f3.checkbox("Только спорные", key="rv_fl")
    only_new = f4.checkbox("Без решения", key="rv_new")
    size = f5.selectbox("На странице", [25, 50, 100], index=1, key="rv_size")
    sel = filter_rows(rows, "flagged" if only_fl else "all", cat, q, langs)
    if only_new:
        sel = [r for r in sel if not dec.get(r["id"], {}).get("verdict")]
    pages = max(1, -(-len(sel) // size))
    if st.session_state.get("rv_page", 1) > pages:
        st.session_state["rv_page"] = 1
    page = st.number_input(f"Страница (из {pages}) · найдено слов: {len(sel)}", 1, pages, 1, key="rv_page")
    chunk = sel[(page - 1) * size: page * size]

    with st.expander("Решения: применить · экспорт · импорт · сброс"):
        a1, a2, a3 = st.columns(3)
        if a1.button("Применить к YAML", type="primary", help="✗ — удалить слова, правки записать в YAML"):
            n = apply_decisions(root)
            _bump("words_rv")
            notify.report("success", f"Применено: правок {n['edit']}, удалено слов {n['del']}")
            st.rerun()
        a2.download_button("Экспорт решений (decisions.json)", decisions_json(dec),
                           file_name="decisions.json", mime="application/json")
        sure = a3.checkbox("Подтверждаю сброс", key="rv_sure")
        if a3.button("Сбросить всё") and sure:
            save_decisions(root, {})
            _bump("words_rv")
            st.rerun()
        up = st.file_uploader("Импорт решений (decisions.json)", type="json", key=f"rv_up_{st.session_state.get('words_rv', 0)}")
        if up is not None and st.button("Загрузить решения"):
            try:
                n = merge_decisions(dec, json.loads(up.getvalue().decode("utf-8")))
            except (ValueError, AttributeError) as exc:
                notify.report("error", "Не удалось прочитать файл", details=[str(exc)])
            else:
                save_decisions(root, dec)
                _bump("words_rv")
                notify.report("success", f"Загружено решений: {n}")
                st.rerun()

    ver = st.session_state.get("words_rv", 0)
    shown = ["ru", "en"] + [l for l in langs if l not in ("ru", "en")]
    widths = [1.3] + [2] * len(shown) + [1.4, 2.3, 3]
    head = st.columns(widths)
    for col, t in zip(head, ["Решение"] + [lang_label(l) for l in shown] + ["Часть речи", "Слово", "Замечания"]):
        col.markdown(f"**{t}**")
    for r in chunk:
        wid, e = r["id"], dec.get(r["id"], {})
        cols = st.columns(widths)
        b1, b2 = cols[0].columns(2)
        v = e.get("verdict", "")
        b1.button("✓", key=f"rv_ok_{ver}_{wid}", on_click=_cb_toggle, args=(wid, "ok"),
                  type="primary" if v == "ok" else "secondary")
        b2.button("✗", key=f"rv_del_{ver}_{wid}", on_click=_cb_toggle, args=(wid, "del"),
                  type="primary" if v == "del" else "secondary")
        for col, l in zip(cols[1:1 + len(shown)], shown):
            orig = r["tr"].get(l, "")
            staged = e.get(l) if l in ("ru", "en") else e.get("tr", {}).get(l)
            key = f"rv_{ver}_{wid}_{l}"
            col.text_input(lang_label(l), value=staged or orig, key=key, label_visibility="collapsed",
                           on_change=_cb_stage, args=(wid, l, key, orig))
        pkey = f"rv_{ver}_{wid}_pos"
        cur = e.get("pos", r["pos"])
        cols[-3].selectbox("Часть речи", POS, index=POS.index(cur), key=pkey, format_func=POS_RU.get,
                           label_visibility="collapsed", on_change=_cb_stage, args=(wid, "pos", pkey, r["pos"]))
        cols[-2].markdown(f"{cat_label(r['cat'])}  \n`{wid}` · {r['age'][0]}–{r['age'][1]} лет · пр. {r['prio']}")
        mark = {"ok": ":green[✓ ок] ", "del": ":red[✗ удалить] "}.get(v, "")
        cols[-1].markdown(mark + " ".join(f":orange[{f}]" for f in r["flags"]) + (f"  \n_{r['note']}_" if r["note"] else ""))


def _table(root: Path, rows: list[dict], langs: list[str]) -> None:
    import pandas as pd

    cats = ["все"] + sorted({r["cat"] for r in rows}, key=cat_label)
    c1, c2, c3 = st.columns([2, 2, 3])
    cat = c1.selectbox("Категория", cats, format_func=lambda c: "Все" if c == "все" else cat_label(c))
    mode = c2.selectbox("Показать", list(MODES), format_func=MODES.get)
    q = c3.text_input("Поиск (id или перевод)")
    sel = filter_rows(rows, mode, cat, q, langs)
    st.caption(f"Показано {min(len(sel), 300)} из {len(sel)} (всего слов: {len(rows)}).")
    sel = sel[:300]
    lcol = {lang_label(l): l for l in langs}
    df = pd.DataFrame([{"id": r["id"], "Категория": cat_label(r["cat"]), "Часть речи": POS_RU[r["pos"]],
                        "Ревью": REVIEW_RU[r["review"]],
                        **{lang_label(l): r["tr"].get(l, "") for l in langs},
                        "Картинка": r["img"], "Озвучка": ",".join(r["audio"]),
                        "Флаги": "; ".join(r["flags"])} for r in sel])
    if df.empty:
        st.info("Нет слов по выбранным условиям.")
        return
    key = f"words_ed_{st.session_state.get('words_ver', 0)}"
    edited = st.data_editor(
        df, key=key, hide_index=True, use_container_width=True,
        disabled=["id", "Категория", "Картинка", "Озвучка", "Флаги"],
        column_config={"Часть речи": st.column_config.SelectboxColumn(options=list(POS_FROM)),
                       "Ревью": st.column_config.SelectboxColumn(options=list(REVIEW_FROM))})
    if not st.button("Сохранить правки", type="primary"):
        return
    dec, n = load_decisions(root), 0
    for old, new in zip(df.to_dict("records"), edited.to_dict("records")):
        tr = {c: new[l].strip() for l, c in lcol.items() if new[l].strip() and new[l] != old[l]}
        pos = POS_FROM[new["Часть речи"]]
        pos_changed = new["Часть речи"] != old["Часть речи"]
        if tr or pos_changed:
            edit_word(root, old["id"], tr=tr, pos=pos if pos_changed else None)
            n += 1
        if new["Ревью"] != old["Ревью"]:
            stage(dec, old["id"], "verdict", REVIEW_FROM.get(new["Ревью"], ""))
            n += 1
    save_decisions(root, dec)
    _bump("words_ver")
    notify.report("success", f"Сохранено правок: {n}")
    st.rerun()


def _add(root: Path, rows: list[dict], langs: list[str]) -> None:
    ids = {r["id"] for r in rows}
    cats = sorted({r["cat"] for r in rows}, key=cat_label)
    with st.form("words_add"):
        c = st.columns(3)
        cat = c[0].selectbox("Категория", cats, format_func=cat_label)
        newcat = c[1].text_input("Новая категория (id, латиница; если не из списка)")
        wid = c[2].text_input("id слова (латиница)")
        c = st.columns(2)
        pos = c[0].selectbox("Часть речи", list(POS_RU), format_func=POS_RU.get)
        prio = c[1].selectbox("Приоритет (1 — высокий, 3 — низкий)", [1, 2, 3], index=1)
        vals = {l: st.text_input(f"Перевод: {lang_label(l)}") for l in langs}
        ok = st.form_submit_button("Добавить слово", type="primary")
    if ok:
        try:
            add_word(root, newcat.strip() or cat, wid, vals.get("ru", ""), pos, prio,
                     {l: v for l, v in vals.items() if l != "ru"}, ids)
        except ValueError as e:
            notify.report("error", "Слово не добавлено", details=[str(e)])
        else:
            notify.report("success", f"Добавлено: {wid}")
            st.rerun()
    st.divider()
    lc, bc = st.columns([3, 1])
    new = lc.text_input("Новый язык (код: en, de, kk…)", key="words_newlang")
    if bc.button("Добавить язык") and LANG_RE.match(new or ""):
        st.session_state.setdefault("words_langs", [])
        if new not in st.session_state["words_langs"]:
            st.session_state["words_langs"].append(new)
        st.rerun()


def _check(root: Path, rows: list[dict], langs: list[str]) -> None:
    cols = st.columns(len(langs))
    for col, l in zip(cols, langs):
        col.metric(f"Нет перевода: {lang_label(l)}", sum(l not in r["tr"] for r in rows))
    st.write(f"Без картинки: **{sum(not r['img'] for r in rows)}**; "
             f"дубли: **{len(filter_rows(rows, 'dups', 'все', '', langs))}**; "
             f"помечено ✗: **{sum(r['review'] == 'del' for r in rows)}**")
    b = st.columns(4)
    if b[0].button("Проверить"):
        rc, out = run_validate(root)
        notify.report("success" if rc == 0 else "error", "Проверка словаря", details=[out[-2000:]])
    if b[1].button("Экспорт"):
        rc, out = run_export(root)
        notify.report("success" if rc == 0 else "error", "Экспорт", details=[out[-2000:]])
    if b[2].button("Применить решения"):
        n = apply_decisions(root)
        _bump("words_rv")
        notify.report("success", f"Применено: правок {n['edit']}, удалено слов {n['del']}")
        st.rerun()
    st.divider()
    cur = _run(root, "git", "branch", "--show-current")[1]
    branch = st.text_input("Ветка", value=cur)
    msg = st.text_input("Сообщение коммита", value="words: правки из админки")
    if st.button("Закоммитить в ветку"):
        rc, out = commit(root, branch, msg)
        notify.report("success" if rc == 0 else "error", "Коммит", details=[out[-2000:]])


def render() -> None:
    root = words_dir()
    if not (root / "words").is_dir():
        st.error(f"Нет каталога словаря: {root}. Задайте DS_WORDS_DIR.")
        return
    st.caption(f"Данные: `{root}` (YAML репозитория ds_words). Вкладка только читает и пишет файлы.")
    try:
        rows, langs = load_rows(root)
    except Exception as exc:  # noqa: BLE001
        notify.report("error", "Не удалось загрузить словарь", details=[str(exc)])
        return
    langs = langs_of(rows, st.session_state.get("words_langs"))
    t0, t1, t2, t3 = st.tabs(["Ревью", "Таблица", "Добавить слово", "Проверка и коммит"])
    with t0:
        _review(root, rows, langs)
    with t1:
        _table(root, rows, langs)
    with t2:
        _add(root, rows, langs)
    with t3:
        _check(root, rows, langs)

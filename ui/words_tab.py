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
from ui.table_utils import action_row, column_settings, table_slots

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
REVIEW_RU = {"": "—", "ok": "✓ ок", "del": "✗ удалить"}
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
                     "tr": w["tr"], "flags": flags.get(w["id"], []), "img": img or "",
                     "audio": sorted(aud), "review": dec.get(w["id"], {}).get("verdict", "")})
    return rows, langs_of(rows)


def langs_of(rows: list[dict], extra: list[str] | None = None) -> list[str]:
    ls = {l for r in rows for l in r["tr"]} | set(extra or []) | {"ru"}
    return ["ru"] + sorted(ls - {"ru"})


def filter_rows(rows: list[dict], mode: str, cat: str, q: str, langs: list[str], *, pos: str = "",
                prio: int = 0, img: str = "", aud: str = "", verdict: str = "", age: str = "") -> list[dict]:
    q = q.strip().lower()
    out = []
    for r in rows:
        if cat and cat != "все" and r["cat"] != cat:
            continue
        if q and q not in r["id"].lower() and not any(q in v.lower() for v in r["tr"].values()):
            continue
        if pos and r["pos"] != pos:
            continue
        if prio and r["prio"] != prio:
            continue
        if img and bool(r["img"]) != (img == "есть"):
            continue
        if aud and bool(r["audio"]) != (aud == "есть"):
            continue
        if verdict and r["review"] != (verdict if verdict != "none" else ""):
            continue
        if age and f"{r['age'][0]}–{r['age'][1]}" != age:
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


def run_imggen(root: Path, ids: list[str]) -> tuple[int, str]:
    """Генерация/перегенерация картинок (ds_words/scripts/imggen.py, ключ ~/.neuraldeep_key)."""
    return _run(root, sys.executable, "scripts/imggen.py", "gen", "--ids", ",".join(ids), "--force")


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

GEN_HELP = (
    "Генерирует картинки для отмеченных строк (Qwen-Image-2.1), по очереди, ≈0,5–1 мин на слово; "
    "страница ждёт окончания.\n\n"
    "• Картинка уже есть — будет заменена новой, прежний файл не сохраняется (откат только через git), "
    "статус вернётся в «generated», утверждение сбросится.\n"
    "• Промпт: единый стиль v1 + описание слова; для слов без своего описания берётся сам перевод. "
    "Для людей, частей тела, действий и абстракций особых промптов пока нет — результат может быть неточным.\n"
    "• Файлы и реестр (images/, registry/images.json) меняются в рабочей папке ds_words без коммита.\n"
    "• Ссылка в колонке «Картинка» обновится после перерисовки страницы.")


def _bump(key: str) -> None:
    st.session_state[key] = st.session_state.get(key, 0) + 1


_TB_KEYS = ("tb_q", "tb_cat", "tb_mode", "tb_pos", "tb_prio", "tb_img", "tb_aud", "tb_ver", "tb_age",
            "tb_fl", "tb_size", "tb_page")


_TB_TYPES = {"tb_prio": int, "tb_size": int, "tb_page": int, "tb_fl": bool}
_TB_DEF = {"tb_cat": "все", "tb_mode": next(iter(MODES)), "tb_size": 50, "tb_page": 1}
_HOST_WORDS_ROOT = os.environ.get("HOST_WORDS_ROOT", "/home/vector/projects/ds_words")
_WSL_DISTRO = os.environ.get("HOST_WSL_DISTRO", "Ubuntu")


def img_uri(rel: str) -> str | None:
    """dsdoc://-ссылка (как в «Документах»): хост открывает файл программой по умолчанию."""
    return f"dsdoc://{_WSL_DISTRO}{_HOST_WORDS_ROOT}/{rel}" if rel else None


def _tb_restore(valid: dict) -> None:
    """Один раз за сессию: фильтры из query params -> session_state (переживает F5)."""
    if st.session_state.get("_tb_restored"):
        return
    st.session_state["_tb_restored"] = True
    for k in _TB_KEYS:
        v = st.query_params.get(k)
        if v is None or k in st.session_state:
            continue
        t = _TB_TYPES.get(k, str)
        try:
            v = (v == "1") if t is bool else t(v)
        except ValueError:
            continue
        if k in valid and v not in valid[k]:
            continue
        st.session_state[k] = v


def _tb_save() -> None:
    for k in _TB_KEYS:
        v = st.session_state.get(k, _TB_DEF.get(k, ""))
        if v is True:
            v = "1"
        if v in (None, "", 0, False) or v == _TB_DEF.get(k):
            st.query_params.pop(k, None)
        elif st.query_params.get(k) != str(v):
            st.query_params[k] = str(v)


def _reset_tb() -> None:
    for k in _TB_KEYS:
        st.session_state.pop(k, None)


def _table(root: Path, rows: list[dict], langs: list[str]) -> None:
    import pandas as pd

    dec = load_decisions(root)
    c = counts(dec)
    st.caption(f"✓ ок: {c['ok']} · ✗ удалить: {c['del']} · с правками: {c['edit']} · всего слов: {len(rows)}. "
               "Правки и решения копятся в черновике и попадают в YAML кнопкой «Применить к YAML».")
    cats = ["все"] + sorted({r["cat"] for r in rows}, key=cat_label)
    ALL = "все"
    ages = sorted({f"{r['age'][0]}–{r['age'][1]}" for r in rows})
    _tb_restore({"tb_cat": cats, "tb_mode": list(MODES), "tb_ver": ["", "none", "ok", "del"],
                 "tb_prio": [0, 1, 2, 3], "tb_pos": ["", *POS], "tb_img": ["", "есть", "нет"],
                 "tb_aud": ["", "есть", "нет"], "tb_age": ["", *ages], "tb_size": [25, 50, 100, 300]})
    with st.container(key="cmpv_words"):
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        q = c1.text_input("Поиск (id или перевод)", key="tb_q")
        cat = c2.selectbox("Категория", cats, key="tb_cat", width=220,
                           format_func=lambda x: "Все" if x == "все" else cat_label(x))
        mode = c3.selectbox("Показать", list(MODES), key="tb_mode", width=170, format_func=MODES.get)
        verdict = c4.selectbox("Решение", ["", "none", "ok", "del"], key="tb_ver", width=170,
                               format_func=lambda x: {"": "Все", "none": "Без решения"}.get(x) or REVIEW_RU[x])
        prio = c5.selectbox("Приоритет", [0, 1, 2, 3], key="tb_prio", width=120,
                            format_func=lambda x: str(x) if x else "Все")
        with c6.popover("⚙️", help="Дополнительные фильтры"):
            pos = st.selectbox("Часть речи", ["", *POS], key="tb_pos", format_func=lambda x: POS_RU.get(x, "Все"))
            img = st.selectbox("Картинка", ["", "есть", "нет"], key="tb_img", format_func=lambda x: x or "Все")
            aud = st.selectbox("Озвучка", ["", "есть", "нет"], key="tb_aud", format_func=lambda x: x or "Все")
            age = st.selectbox("Возраст", ["", *ages], key="tb_age", format_func=lambda x: x or "Все")
            only_fl = st.checkbox("Только спорные", key="tb_fl")
            size = st.selectbox("Слов на странице", [25, 50, 100, 300], index=1, key="tb_size")
        c7.button("Сбросить", key="tb_reset", on_click=_reset_tb)
    sel = filter_rows(rows, mode, cat, q, langs, pos=pos, prio=prio, img=img, aud=aud, verdict=verdict, age=age)
    if only_fl:
        sel = [r for r in sel if r["flags"]]
    pages = max(1, -(-len(sel) // size))
    if st.session_state.get("tb_page", 1) > pages:
        st.session_state["tb_page"] = 1
    page = st.number_input(f"Страница (из {pages}) · найдено слов: {len(sel)}", 1, pages, 1, key="tb_page")
    chunk = sel[(page - 1) * size: page * size]
    _tb_save()

    with st.expander("Решения: применить · экспорт · импорт · сброс"):
        a1, a2, a3 = st.columns(3)
        if a1.button("Применить к YAML", type="primary", help="✗ — удалить слова, правки записать в YAML"):
            n = apply_decisions(root)
            _bump("words_ver")
            notify.report("success", f"Применено: правок {n['edit']}, удалено слов {n['del']}")
            st.rerun()
        a2.download_button("Экспорт решений (decisions.json)", decisions_json(dec),
                           file_name="decisions.json", mime="application/json")
        sure = a3.checkbox("Подтверждаю сброс", key="tb_sure")
        if a3.button("Сбросить всё") and sure:
            save_decisions(root, {})
            _bump("words_ver")
            st.rerun()
        up = st.file_uploader("Импорт решений (decisions.json)", type="json",
                              key=f"tb_up_{st.session_state.get('words_ver', 0)}")
        if up is not None and st.button("Загрузить решения"):
            try:
                n = merge_decisions(dec, json.loads(up.getvalue().decode("utf-8")))
            except (ValueError, AttributeError) as exc:
                notify.report("error", "Не удалось прочитать файл", details=[str(exc)])
            else:
                save_decisions(root, dec)
                _bump("words_ver")
                notify.report("success", f"Загружено решений: {n}")
                st.rerun()

    if not chunk:
        st.info("Нет слов по выбранным условиям.")
        return
    shown = [l for l in ("ru", "en") if l in langs] + [l for l in langs if l not in ("ru", "en")]
    lcol = {lang_label(l): l for l in shown}
    recs = []
    for r in chunk:
        e = dec.get(r["id"], {})
        row = {"Решение": REVIEW_RU[e.get("verdict", "")], "id": r["id"], "Категория": cat_label(r["cat"]),
               "Возраст": f"{r['age'][0]}–{r['age'][1]}", "Приоритет": r["prio"]}
        for l in shown:
            staged = e.get(l) if l in ("ru", "en") else e.get("tr", {}).get(l)
            row[lang_label(l)] = staged or r["tr"].get(l, "")
        row.update({"Часть речи": POS_RU[e.get("pos", r["pos"])], "Картинка": img_uri(r["img"]),
                    "Озвучка": ",".join(r["audio"]), "Заметка": r["note"], "Флаги": "; ".join(r["flags"])})
        recs.append(row)
    df = pd.DataFrame(recs)
    df.insert(0, "Выбор", False)
    key = f"words_ed_{st.session_state.get('words_ver', 0)}"
    tbl, cap_col, gear_col = table_slots("words")
    order, config, sort = column_settings(
        "words", {c: c for c in df.columns},
        {"Часть речи": st.column_config.SelectboxColumn(options=list(POS_FROM)),
         "Решение": st.column_config.SelectboxColumn(options=list(REVIEW_FROM)),
         "Выбор": st.column_config.CheckboxColumn("Выбор", width="small"),
         "Картинка": st.column_config.LinkColumn("Картинка", display_text=":material/image:", width="small")},
        pinned=("Выбор", "Решение", "id"), host=gear_col)
    if sort:
        df = df.sort_values(sort[0], ascending=sort[1], kind="stable")
    cap_col.caption(f"Строк: {len(df)}")
    edited = tbl.data_editor(
        df, key=key, hide_index=True, use_container_width=True, column_order=order, column_config=config,
        disabled=["id", "Категория", "Возраст", "Приоритет", "Картинка", "Озвучка", "Заметка", "Флаги"])
    picked = edited.loc[edited["Выбор"], "id"].tolist()
    g1, g2, g3 = action_row(3, "words")
    if g3.button(f"Сгенерировать картинку ({len(picked)})", disabled=not picked, key="words_gen_btn",
                 help=GEN_HELP):
        with st.spinner(f"Генерация: {len(picked)} шт., по очереди…"):
            rc, out = run_imggen(root, picked)
        notify.report("success" if rc == 0 else "error", "Генерация картинок", details=[out[-1500:]])
        st.rerun()
    if not st.button("Сохранить в черновик", type="primary"):
        return
    by_id, n = {r["id"]: r for r in chunk}, 0
    for old, new in zip(df.to_dict("records"), edited.to_dict("records")):
        r, wid = by_id[old["id"]], old["id"]
        if new["Решение"] != old["Решение"]:
            stage(dec, wid, "verdict", REVIEW_FROM.get(new["Решение"], ""))
            n += 1
        for lab, code in lcol.items():
            if new[lab] != old[lab]:
                stage(dec, wid, code, (new[lab] or "").strip(), r["tr"].get(code, ""))
                n += 1
        if new["Часть речи"] != old["Часть речи"]:
            stage(dec, wid, "pos", POS_FROM[new["Часть речи"]], r["pos"])
            n += 1
    save_decisions(root, dec)
    _bump("words_ver")
    notify.report("success", f"В черновик: изменений {n}")
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
        _bump("words_ver")
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
    t1, t2, t3 = st.tabs(["Таблица", "Добавить слово", "Проверка и коммит"])
    with t1:
        _table(root, rows, langs)
    with t2:
        _add(root, rows, langs)
    with t3:
        _check(root, rows, langs)

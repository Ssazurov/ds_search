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
VOTE_RU = {"": "Все", "up": "👍", "down": "👎", "none": "Без оценки"}
VOTE_ICON = {"up": "👍", "down": "👎"}


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
    ap = root / "registry" / "audio.json"
    areg = json.loads(ap.read_text("utf-8")) if ap.exists() else {}
    rows = []
    for w in words:
        img, aud = W.media(w["id"])
        rows.append({"stress": areg.get(w["id"], {}).get("ru", {}).get("stress"), "id": w["id"], "cat": w["category"], "pos": w["pos"], "prio": w["prio"],
                     "age": w["age"], "note": w.get("note") or "", "hint": w.get("hint") or "",
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
    for k in ("ru", "en", "note", "hint"):
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
    box = e if field in ("verdict", "pos", "ru", "en", "note", "hint") else e.setdefault("tr", {})
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


def _set_field(line: str, key: str, val: str) -> str:
    """Задать скаляр key в строке-flow-mapping {id: .., ...}; старое значение убирается."""
    line = re.sub(r',\s*%s:\s*("(?:[^"\\]|\\.)*"|[^,}]*)' % key, "", line, count=1)
    i = line.rfind("}")
    return line[:i] + ", %s: %s" % (key, json.dumps(val, ensure_ascii=False)) + line[i:]


def edit_word(root: Path, wid: str, *, tr: dict[str, str] | None = None,
              pos: str | None = None, delete: bool = False, note: str | None = None,
              hint: str | None = None) -> bool:
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
                if note:
                    ln = _set_field(ln, "note", note)
                if hint:
                    ln = _set_field(ln, "hint", hint)
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
        if tr or e.get("pos") or e.get("note") or e.get("hint"):
            n["edit"] += int(edit_word(root, wid, tr=tr, pos=e.get("pos"),
                                       note=e.get("note"), hint=e.get("hint")))
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


def hint_en(text: str) -> str:
    """Подсказка для картинки: русский → английский (LLM), английский как есть."""
    if not re.search("[а-яё]", text, re.I):
        return text
    from src.news.llm_draft import call_llm, load_llm_config
    p = "Translate to English for an image-generation prompt. Output only the translation, no quotes:\n" + text
    out = call_llm(p, load_llm_config(), purpose="news", input_chars=len(text)).strip()
    if out.startswith(("{", "[", "```")):  # GAR/LLM может вернуть JSON-обёртку
        try:
            obj = json.loads(out.strip("`").removeprefix("json").strip())
            vals = obj.values() if isinstance(obj, dict) else obj
            out = next((v for v in vals if isinstance(v, str) and v.strip()), "")
        except Exception:
            out = re.sub(r"[{}\[\]\"]|^\w+\s*:", " ", out)
    out = out.strip().strip('"\'“”')
    if not out or re.search("[а-яё]", out, re.I):
        raise ValueError(f"перевод подсказки не удался: {text!r}")
    return out


def record_feedback(root: Path, reg: dict, hints: dict[str, str]) -> None:
    """Перед перегенерацией: если у картинки стоит голос (👍/👎 в Просмотре), фиксируем текущую
    сцену в историю registry/feedback.json. Сам голос в registry/images.json не трогаем —
    он сбросится сам, когда картинку перезапишет новая генерация."""
    for wid, h in hints.items():
        v = reg.get(wid, {}).get("vote")
        h = (h or "").strip()
        if v and h:
            try:
                _run(root, sys.executable, "scripts/imggen.py", "feedback", wid, v, hint_en(h))
            except Exception:
                pass


def load_images_reg(root: Path) -> dict:
    f = root / "registry" / "images.json"
    return json.loads(f.read_text("utf-8")) if f.exists() else {}


def load_avotes(root: Path) -> dict:
    f = root / "registry" / "audio_votes.json"
    return json.loads(f.read_text("utf-8")) if f.exists() else {}


def set_avote(root: Path, wid: str, v: str) -> None:
    d = load_avotes(root)
    if v:
        d[wid] = v
    else:
        d.pop(wid, None)
    (root / "registry" / "audio_votes.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")


def _ask(kind: str, pressed: bool, tgt: list, reg: dict) -> bool:
    """Перегенерация: если у кого-то из целей стоит 👍 — не запускаем, просим подтверждение (_cf)."""
    if pressed and any(reg.get(i) == "up" for i in tgt):
        st.session_state["_cf"] = kind
        return False
    return pressed


def set_vote(root: Path, wid: str, v: str, scene: str = "") -> None:
    cmd = [sys.executable, "scripts/imggen.py", "vote", wid, v or "clear"]
    if scene:
        cmd += ["--scene", scene]
    _run(root, *cmd)


def run_imggen(root: Path, ids: list[str], hints: dict[str, str] | None = None) -> tuple[int, str]:
    """Генерация/перегенерация картинок (ds_words/scripts/imggen.py, ключ ~/.neuraldeep_key).
    hints {id: подсказка (ru/en)} — переводится на английский и добавляется в промпт."""
    cmd = [sys.executable, "scripts/imggen.py", "gen", "--ids", ",".join(ids), "--force"]
    hints = {i: h for i, h in (hints or {}).items() if i in ids and h}
    if not hints:
        return _run(root, *cmd)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({i: hint_en(h) for i, h in hints.items()}, f, ensure_ascii=False)
    try:
        return _run(root, *cmd, "--hints", f.name)
    finally:
        os.unlink(f.name)


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
            "tb_fl", "tb_vote", "tb_avote", "tb_hint", "tb_size", "tb_page")


_TB_TYPES = {"tb_prio": int, "tb_size": int, "tb_page": int, "tb_fl": bool}
_TB_DEF = {"tb_cat": "все", "tb_mode": next(iter(MODES)), "tb_size": 50, "tb_page": 1}
_HOST_WORDS_ROOT = os.environ.get("HOST_WORDS_ROOT", "/home/vector/projects/ds_words")
_WSL_DISTRO = os.environ.get("HOST_WSL_DISTRO", "Ubuntu")


def img_uri(rel: str) -> str | None:
    """dsdoc://-ссылка (как в «Документах»): хост открывает файл программой по умолчанию."""
    return f"dsdoc://{_WSL_DISTRO}{_HOST_WORDS_ROOT}/{rel}" if rel else None


@st.cache_data(show_spinner=False, max_entries=3000)
def _b64(path: str, mtime: float) -> str:
    import base64
    return base64.b64encode(Path(path).read_bytes()).decode()


# клик по ссылке «Озвучка» (https://ds-audio.invalid/<lang>/<id>.mp3) -> играем звук в странице, окно не открываем
_APLAY_JS = (r"if(p.__aplay)return;p.__aplay=1;const o=p.open.bind(p);let a=null;"
             r"p.open=function(u){const m=typeof u==='string'&&u.match(/^https:\/\/ds-audio\.invalid\/(.+)\.mp3/);"
             r"if(m&&p.__amap[m[1]]){if(a)a.pause();a=new p.Audio('data:audio/mpeg;base64,'+p.__amap[m[1]]);a.play();return null;}"
             r"return o.apply(p,arguments);};")


def audio_uri(r: dict) -> str | None:
    """Ссылка на озвучку (ru, иначе первый язык); нет звука -> None (пустая ячейка)."""
    langs = r["audio"]
    if not langs:
        return None
    lang = "ru" if "ru" in langs else langs[0]
    return f"https://ds-audio.invalid/{lang}/{r['id']}.mp3"


TTS_URL = os.environ.get("TTS_URL", "http://host.docker.internal:8790")
# имя -> (min, max, step, default, подпись/подсказка)
TTS_RU = {"exaggeration": "Выразительность", "cfg_weight": "Следование образцу и темп", "temperature": "Случайность",
          "top_p": "Ядро выборки (top-p)", "min_p": "Мин. вероятность (min-p)", "repetition_penalty": "Штраф за повторы",
          "tempo": "Скорость речи", "pad": "Тишина после слова, с", "margin": "Запас перед обрезкой хвоста, с",
          "tail_semi": "Снижение тона в конце, полутонов", "tail_ms": "Длина снижения тона, мс"}
TTS_PARAMS = {
    "exaggeration": (0.25, 2.0, 0.05, 0.2, "Выразительность: ниже = ровнее"),
    "cfg_weight": (0.0, 1.0, 0.05, 0.5, "CFG/темп: ниже = медленнее, ровнее"),
    "temperature": (0.05, 2.0, 0.05, 0.2, "Случайность: ниже = стабильнее"),
    "top_p": (0.1, 1.0, 0.05, 1.0, "Top-p: ниже = консервативнее"),
    "min_p": (0.0, 0.5, 0.01, 0.05, "Min-p: отсечка маловероятных"),
    "repetition_penalty": (1.0, 3.0, 0.1, 2.0, "Штраф повторов"),
    "tempo": (0.5, 1.5, 0.01, 0.87, "Скорость речи (<1 медленнее)"),
    "pad": (0.0, 3.0, 0.1, 1.0, "Тишина после слова, с"),
    "margin": (0.0, 0.5, 0.05, 0.15, "Запас перед обрезкой хвоста, с"),
    "tail_semi": (-3.0, 4.0, 0.25, 1.5, "Плавно понизить тон к концу слова (полутонов); 0 = выкл, минус = повысить"),
    "tail_ms": (50.0, 500.0, 10.0, 250.0, "Сколько последних мс слова снижается тон"),
}


def tts_params() -> dict:
    return {k: float(st.session_state.get(f"tts_{k}", v[3])) for k, v in TTS_PARAMS.items()}


def _tts_reset() -> None:
    for k, v in TTS_PARAMS.items():
        st.session_state[f"tts_{k}"] = v[3]


_REF_EXT = (".wav", ".mp3", ".flac", ".ogg", ".m4a")


def _refs(root: Path) -> list[str]:
    v = root / "voice"
    ps = [*v.glob("*"), *(v / "refs").glob("*")]
    return sorted(str(p.relative_to(root)) for p in ps if p.suffix.lower() in _REF_EXT)


def load_profiles(root: Path) -> dict:
    f = root / "voice" / "profiles.json"
    d = json.loads(f.read_text("utf-8")) if f.exists() else {}
    d.setdefault("profiles", {})
    if not d["profiles"]:
        d["profiles"]["Основной"] = {"ref": "voice/ref.wav", "params": {k: v[3] for k, v in TTS_PARAMS.items()}}
        d["active"] = "Основной"
    return d


def save_profiles(root: Path, d: dict) -> None:
    (root / "voice").mkdir(exist_ok=True)
    (root / "voice" / "profiles.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")


def _prof_apply(pr: dict) -> None:
    for k, v in TTS_PARAMS.items():
        st.session_state[f"tts_{k}"] = float(pr.get("params", {}).get(k, v[3]))
    st.session_state["tts_ref"] = pr.get("ref", "")


def _prof_load(root: Path) -> None:
    d = load_profiles(root)
    name = st.session_state.get("tts_prof")
    if name in d["profiles"]:
        _prof_apply(d["profiles"][name])
        d["active"] = name
        save_profiles(root, d)


def _prof_save(root: Path) -> None:
    name = (st.session_state.get("tts_newname") or st.session_state.get("tts_prof") or "").strip()
    if not name:
        return
    d = load_profiles(root)
    new = name not in d["profiles"]
    d["profiles"][name] = {"ref": "" if new else st.session_state.get("tts_ref", ""), "params": tts_params()}
    if new:
        st.session_state["tts_ref"] = ""  # новый профиль — без прикреплённого файла
    d["active"] = name
    save_profiles(root, d)
    st.session_state["tts_prof"] = name
    st.session_state["tts_newname"] = ""


def _prof_del(root: Path) -> None:
    d = load_profiles(root)
    d["profiles"].pop(st.session_state.get("tts_prof"), None)
    d = load_profiles_fix(root, d)
    st.session_state["tts_prof"] = d["active"]
    _prof_apply(d["profiles"][d["active"]])
    save_profiles(root, d)


def load_profiles_fix(root: Path, d: dict) -> dict:
    if not d["profiles"]:
        d["profiles"]["Основной"] = {"ref": "voice/ref.wav", "params": {k: v[3] for k, v in TTS_PARAMS.items()}}
    if d.get("active") not in d["profiles"]:
        d["active"] = next(iter(d["profiles"]))
    return d


def _ref_del(root: Path) -> None:
    rel = st.session_state.get("tts_ref", "")
    if not rel or rel == "voice/ref.wav":
        return
    (root / rel).unlink(missing_ok=True)
    d = load_profiles(root)
    for pr in d["profiles"].values():
        if pr.get("ref") == rel:
            pr["ref"] = ""
    save_profiles(root, d)
    st.session_state["tts_ref"] = ""


def _ref_add(root: Path) -> None:
    ver = st.session_state.get("tts_upver", 0)
    up = st.session_state.get(f"tts_up_{ver}")
    if not up:
        return
    dst = root / "voice" / "refs" / Path(up.name).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(up.getvalue())
    st.session_state["tts_ref"] = str(dst.relative_to(root))
    st.session_state["tts_upver"] = ver + 1


def _tts_settings(root: Path) -> None:
    """Последний блок вкладки: профили голоса (референс + параметры); применяются к следующей «Сгенерировать звук»."""
    st.divider()
    with st.expander("Настройки голоса (TTS)", expanded=False):
        d = load_profiles(root)
        names = list(d["profiles"])
        if st.session_state.get("tts_prof") not in names:
            st.session_state["tts_prof"] = d.get("active") if d.get("active") in names else names[0]
            _prof_apply(d["profiles"][st.session_state["tts_prof"]])
        p1, p2, p3, p4, _p5 = st.columns([3, 3, 2, 2, 3], vertical_alignment="bottom", gap="small")
        p1.selectbox("Профиль голоса", names, key="tts_prof", on_change=_prof_load, args=(root,))
        p2.text_input("Имя", key="tts_newname")
        p3.button("Сохранить профиль", key="tts_prof_save", on_click=_prof_save, args=(root,), type="primary")
        p4.button("Удалить профиль", key="tts_prof_del", on_click=_prof_del, args=(root,), disabled=len(names) < 2)
        refs = _refs(root)
        if st.session_state.get("tts_ref") not in ["", *refs]:
            st.session_state["tts_ref"] = ""
        r1, r2 = st.columns([5, 3])
        r1.selectbox("Референс (голос-образец)", ["", *refs], key="tts_ref", format_func=lambda x: x or "— без файла (по умолчанию) —",
                     help="Один файл можно использовать в разных профилях")
        cur_rel = st.session_state.get("tts_ref", "")
        if cur_rel and (root / cur_rel).is_file():
            r1.audio((root / cur_rel).read_bytes())
        r1.button("Удалить выбранный референс", key="tts_ref_del", on_click=_ref_del, args=(root,),
                  disabled=not cur_rel or cur_rel == "voice/ref.wav")
        ver = st.session_state.get("tts_upver", 0)
        up = r2.file_uploader("Загрузить референс (wav/mp3/flac/ogg/m4a)", type=[e[1:] for e in _REF_EXT], key=f"tts_up_{ver}")
        r2.button("Добавить референс", key="tts_up_btn", on_click=_ref_add, args=(root,), disabled=not up)
        st.caption("Референс: 5–15 с чистой речи одного человека, без шума, музыки и эха, ровная нейтральная интонация, "
                   "слова/фразы с обычным понижением в конце, без длинных пауз. Тембр, темп, эмоции и «вопросительность» "
                   "в конце слов наследуются из референса — лучше всего читать список отдельных слов с ровным концом.")
        cols = st.columns(3)
        for n, (k, (lo, hi, step, d0, hlp)) in enumerate(TTS_PARAMS.items()):
            cols[n % 3].slider(TTS_RU.get(k, k), lo, hi, d0, step, key=f"tts_{k}", help=hlp)
        st.button("Сбросить параметры", on_click=_tts_reset, key="tts_reset_btn")
        st.caption("Применяется сразу к следующей кнопке «Сгенерировать звук» (выберите слова в таблице).")


def run_tts(items: list[dict], lang: str = "ru") -> tuple[int, str]:
    """Озвучка через локальный сервис ds_words/scripts/tts_server.py (Chatterbox, клон голоса)."""
    import urllib.request
    req = urllib.request.Request(f"{TTS_URL}/gen",
                                 json.dumps({"lang": lang, "items": items, "params": tts_params(),
                                            "ref": st.session_state.get("tts_ref"), "profile": st.session_state.get("tts_prof")}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60 * len(items) + 60) as f:
            res = json.load(f)
    except Exception as e:
        return 1, f"TTS-сервис недоступен ({TTS_URL}): {e}. Запуск: ~/chatterbox-venv/bin/python scripts/tts_server.py"
    msg = f"готово: {len(res['ok'])}" + (f"; ошибки: {res['err']}" if res["err"] else "")
    return (1 if res["err"] else 0), msg


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


def _tb_set_page(p: int) -> None:
    st.session_state["tb_page"] = p


def _tb_pager(page: int, pages: int, shown: int, total: int) -> None:
    """Одна строка: ‹ 1 … 4 [5] 6 … 20 › + размер страницы (5/10/20/50/100/Все); счётчик ниже."""
    items: list = []
    if pages > 1:
        nums = sorted({1, pages, page - 1, page, page + 1} & set(range(1, pages + 1)))
        items = ["prev"]
        for k, n in enumerate(nums):
            if k and n - nums[k - 1] > 1:
                items.append("gap")
            items.append(n)
        items.append("next")
    items.append("size")
    with st.container(key="pager"):
        with st.container(key="pgnums"):
            for col, it in zip(st.columns(len(items), gap="small", vertical_alignment="center"), items):
                if it == "gap":
                    col.markdown("<div class='pg-gap'>…</div>", unsafe_allow_html=True)
                elif it == "prev":
                    col.button("‹", key="tb_pg_prev", disabled=page <= 1, on_click=_tb_set_page, args=(page - 1,))
                elif it == "next":
                    col.button("›", key="tb_pg_next", disabled=page >= pages, on_click=_tb_set_page, args=(page + 1,))
                elif it == "size":
                    with col.container(key="pgsize"):
                        st.segmented_control("На странице", [5, 10, 20, 50, 100, 0], default=50, key="tb_size",
                                             format_func=lambda x: str(x) if x else "Все", label_visibility="collapsed")
                else:
                    col.button(str(it), key=f"tb_pg_{it}", on_click=_tb_set_page, args=(it,),
                               type="primary" if it == page else "secondary")
        with st.container(key="pgfoot"):
            st.caption(f"{shown} из {total} · стр. {page} из {pages}")


_SHIFT_CODE = r"""(function(){
  let shiftDown=false, last=null, force=false; const skip=new Set();
  const st=document.createElement('style');
  st.textContent='[class*="st-key-cmp_pv"] ~ * img, [data-testid="stColumn"]:has([class*="st-key-pv_"]) img{cursor:pointer}';
  document.head.appendChild(st);
  document.addEventListener('keydown',function(e){if(e.key==='Shift')shiftDown=true;},true);
  document.addEventListener('keyup',function(e){if(e.key==='Shift')shiftDown=false;},true);
  window.addEventListener('blur',function(){shiftDown=false;});
  document.addEventListener('click',function(e){
    const t=e.target;
    const sel='[class*="st-key-pv_"] input[type="checkbox"]';
    if(t instanceof HTMLImageElement){
      const col=t.closest('[data-testid="stColumn"]');
      const cb=col&&col.querySelector(sel);
      if(cb){force=e.shiftKey||shiftDown;cb.click();force=false;}
      return;
    }
    if(!(t instanceof HTMLInputElement)||t.type!=='checkbox'||!t.matches(sel))return;
    if(skip.has(t)){skip.delete(t);return;}
    const list=Array.from(document.querySelectorAll(sel));
    const i=list.indexOf(t);
    const j=(last&&document.contains(last))?list.indexOf(last):-1;
    if((e.shiftKey||shiftDown||force)&&j>=0&&j!==i){
      const a=Math.min(i,j), b=Math.max(i,j), want=t.checked;
      let n=0;
      for(let k=a;k<=b;k++){const el=list[k];
        if(el!==t&&el.checked!==want){skip.add(el);setTimeout(function(){el.click();},40*(++n));}}
    }
    last=t;
  },true);
})();"""


PREV_MAX = 50  # максимум картинок в Просмотре


def _toggle_prev() -> None:
    st.session_state["tb_prev"] = not st.session_state.get("tb_prev", True)


def _selall_cb() -> None:
    """«Выбрать все»: только видимые строки на текущей странице."""
    ids = set(st.session_state.get("_tb_vis", []))
    sel = st.session_state.setdefault("tb_sel", set())
    if st.session_state.get("tb_selall"):
        sel |= ids
    else:
        sel -= ids
    st.session_state["tb_selver"] = st.session_state.get("tb_selver", 0) + 1


def _mark_all(ids: list[str]) -> None:
    for i in ids:
        st.session_state[f"pv_{i}"] = True


def _clear_marks(ids: list[str]) -> None:
    for i in ids:
        st.session_state[f"pv_{i}"] = False


def _grid_cols(n: int, w: int = 1100, h: int = 700, cap: int = 48, gap: int = 16, max_cols: int = 5) -> int:
    """Число колонок сетки (не больше max_cols), при котором квадратные карточки максимально крупные."""
    return min(n, max_cols)


def _preview(root: Path, picked_rows: list[dict]) -> None:
    """Поле просмотра: карточки выбранных слов в невидимой сетке, у каждой флажок «отметить
    для перегенерации» (ключ pv_<id>) и пальцы 👍/👎 (ключ th_<id>) — голос за текущую картинку,
    хранится в registry/images.json и сам сбрасывается при следующей генерации."""
    ids = [r["id"] for r in picked_rows]
    marked = sum(bool(st.session_state.get(f"pv_{i}")) for i in ids)
    st.caption(f"Отмечено для перегенерации: {marked} из {len(ids)}")
    with st.container(key="cmp_pvbar"):
        b1, b2 = st.columns(2, vertical_alignment="center")
        b1.button("Выбрать все", key="pv_all", on_click=_mark_all, args=(ids,), disabled=marked == len(ids))
        b2.button("Снять отметки", key="pv_clear", on_click=_clear_marks, args=(ids,), disabled=not marked)
    reg = load_images_reg(root)
    areg = load_avotes(root)
    cols = _grid_cols(len(ids))
    for i in range(0, len(picked_rows), cols):
        for col, r in zip(st.columns(cols, gap="small"), picked_rows[i:i + cols]):
            f = root / r["img"] if r["img"] else None
            if f is not None and f.is_file():
                col.image(f.read_bytes(), use_container_width=True)
            else:
                col.caption("нет картинки")
            vote = reg.get(r["id"], {}).get("vote")
            row_cols = col.columns([4, 1, 1, 1, 1], gap="small", vertical_alignment="center")
            row_cols[0].checkbox(r["tr"].get("ru") or r["id"], key=f"pv_{r['id']}")
            row_cols[1].button("", icon=":material/thumb_up:", type="tertiary",
                               key=f"th_up_{'on_' if vote == 'up' else ''}{r['id']}", disabled=not r["img"],
                               on_click=set_vote, args=(root, r["id"], "" if vote == "up" else "up"))
            row_cols[2].button("", icon=":material/thumb_down:", type="tertiary",
                               key=f"th_down_{'on_' if vote == 'down' else ''}{r['id']}", disabled=not r["img"],
                               on_click=set_vote, args=(root, r["id"], "" if vote == "down" else "down"))
            av = areg.get(r["id"])
            row_cols[3].button("", icon=":material/thumb_up:", type="tertiary", help="Звук 👍",
                               key=f"ath_up_{'on_' if av == 'up' else ''}{r['id']}", disabled=not r["audio"],
                               on_click=set_avote, args=(root, r["id"], "" if av == "up" else "up"))
            row_cols[4].button("", icon=":material/thumb_down:", type="tertiary", help="Звук 👎",
                               key=f"ath_down_{'on_' if av == 'down' else ''}{r['id']}", disabled=not r["audio"],
                               on_click=set_avote, args=(root, r["id"], "" if av == "down" else "down"))
    import streamlit.components.v1 as components
    components.html(
        "<script>(function(){const p=window.parent;if(p.__pvShift2)return;p.__pvShift2=1;"
        "const s=p.document.createElement('script');s.textContent=" + json.dumps(_SHIFT_CODE) + ";"
        "p.document.head.appendChild(s);})();</script>", height=0)


def _decisions_block(root: Path, dec: dict) -> None:
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


@st.fragment
def _table(root: Path, rows: list[dict], langs: list[str]) -> None:
    """Фрагмент: фильтры, пагинация, выбор строк, оценки и Просмотр перерисовываются без полной
    перезагрузки страницы. Состояние (решения, оценки) читается с диска при каждом запуске фрагмента;
    долгие/меняющие данные действия (генерация, озвучка, подсказки, применение) делают полный st.rerun()."""
    import pandas as pd

    dec = load_decisions(root)
    c = counts(dec)
    # st.caption(f"✓ ок: {c['ok']} · ✗ удалить: {c['del']} · с правками: {c['edit']} · всего слов: {len(rows)}. "
    #            "Правки и решения копятся в черновике и попадают в YAML кнопкой «Применить к YAML».")
    cats = ["все"] + sorted({r["cat"] for r in rows}, key=cat_label)
    ALL = "все"
    ages = sorted({f"{r['age'][0]}–{r['age'][1]}" for r in rows})
    _tb_restore({"tb_cat": cats, "tb_mode": list(MODES), "tb_ver": ["", "none", "ok", "del"],
                 "tb_prio": [0, 1, 2, 3], "tb_pos": ["", *POS], "tb_img": ["", "есть", "нет"],
                 "tb_aud": ["", "есть", "нет"], "tb_vote": ["", "up", "down", "none"], "tb_avote": ["", "up", "down", "none"], "tb_age": ["", *ages], "tb_size": [5, 10, 20, 50, 100, 0]})
    with st.container(key="cmpv_words"):
        c1, c2, c3, c4, c5, c6, c7, c7a, c8, c9, c10 = st.columns(11)
        q = c1.text_input("Поиск (id или перевод)", key="tb_q")
        cat = c2.selectbox("Категория", cats, key="tb_cat", width=110,
                           format_func=lambda x: "Все" if x == "все" else cat_label(x))
        img = c3.selectbox("Картинка", ["", "есть", "нет"], key="tb_img", width=120,
                           format_func=lambda x: x or "Все")
        mode = c4.selectbox("Показать", list(MODES), key="tb_mode", width=85, format_func=MODES.get)
        verdict = c5.selectbox("Решение", ["", "none", "ok", "del"], key="tb_ver", width=85,
                               format_func=lambda x: {"": "Все", "none": "Без решения"}.get(x) or REVIEW_RU[x])
        prio = c6.selectbox("Приоритет", [0, 1, 2, 3], key="tb_prio", width=60,
                            format_func=lambda x: str(x) if x else "Все")
        vote = c7.selectbox("Оценка", list(VOTE_RU), key="tb_vote", width=80, format_func=VOTE_RU.get)
        avote = c7a.selectbox("Оценка (звук)", list(VOTE_RU), key="tb_avote", width=80, format_func=VOTE_RU.get)
        hint_f = c8.selectbox("Подсказка", ["", "есть", "нет"], key="tb_hint", width=120, format_func=lambda x: x or "Все")
        with c9.popover("⚙️", help="Дополнительные фильтры"):
            pos = st.selectbox("Часть речи", ["", *POS], key="tb_pos", format_func=lambda x: POS_RU.get(x, "Все"))
            aud = st.selectbox("Озвучка", ["", "есть", "нет"], key="tb_aud", format_func=lambda x: x or "Все")
            age = st.selectbox("Возраст", ["", *ages], key="tb_age", format_func=lambda x: x or "Все")
            only_fl = st.checkbox("Только спорные", key="tb_fl")
        c10.button("Сбросить", key="tb_reset", on_click=_reset_tb)
    sel = filter_rows(rows, mode, cat, q, langs, pos=pos, prio=prio, img=img, aud=aud, verdict=verdict, age=age)
    if hint_f:
        sel = [r for r in sel if bool(dec.get(r["id"], {}).get("hint", r["hint"])) == (hint_f == "есть")]
    if only_fl:
        sel = [r for r in sel if r["flags"]]
    votes = {k: (v or {}).get("vote", "") for k, v in load_images_reg(root).items()}
    if vote:
        sel = [r for r in sel if votes.get(r["id"], "") == (vote if vote != "none" else "")]
    size = st.session_state.get("tb_size")
    size = 50 if size is None else size
    size = size or max(1, len(sel))
    pages = max(1, -(-len(sel) // size))
    avotes = load_avotes(root)
    if avote:
        sel = [r for r in sel if avotes.get(r["id"], "") == (avote if avote != "none" else "")]
    size = 50 if size is None else size
    size = size or max(1, len(sel))
    pages = max(1, -(-len(sel) // size))
    sig = (mode, cat, q, pos, prio, img, aud, verdict, age, only_fl, vote, avote, hint_f, size)
    old_sig = st.session_state.get("tb_sig")
    old_page = st.session_state.get("tb_page", 1)
    page = min(max(1, st.session_state.get("tb_page", 1)), pages)
    
    if old_sig != sig:
        st.session_state["tb_sig"] = sig
        st.session_state["tb_page"] = 1
        page = 1
        st.session_state["tb_sel"] = set()
    elif old_page != page:
        st.session_state["tb_sel"] = set()
    
    chunk = sel[(page - 1) * size: page * size]
    _tb_save()

    if not chunk:
        st.info("Нет слов по выбранным условиям.")
        st.divider()
        _decisions_block(root, dec)
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
        row.update({"Часть речи": POS_RU[e.get("pos", r["pos"])], "Картинка": img_uri(r["img"]), "Оценка": VOTE_ICON.get(votes.get(r["id"], ""), ""),
                    "Оценка (звук)": VOTE_ICON.get(avotes.get(r["id"], "")),
                    "Озвучка": audio_uri(r), "Ударение": r.get("stress"), "Заметка": e.get("note", r["note"]),
                    "Подсказка": e.get("hint", r["hint"]), "Флаги": "; ".join(r["flags"])})
        recs.append(row)
    df = pd.DataFrame(recs)
    import hashlib

    sel_set = st.session_state.setdefault("tb_sel", set())
    vis_ids = [r["id"] for r in chunk]
    st.session_state["_tb_vis"] = vis_ids
    st.session_state["_tb_all"] = [r["id"] for r in sel]
    df.insert(0, "Выбор", df["id"].isin(sel_set))
    sig = hashlib.md5("|".join(vis_ids).encode()).hexdigest()[:8]
    key = f"words_ed_{st.session_state.get('words_ver', 0)}_{st.session_state.get('tb_selver', 0)}_{sig}"
    sel_slot = st.container()
    tbl, cap_col, gear_col = table_slots("words")
    order, config, sort = column_settings(
        "words", {c: c for c in df.columns},
        {"Часть речи": st.column_config.SelectboxColumn(options=list(POS_FROM)),
         "Решение": st.column_config.SelectboxColumn(options=list(REVIEW_FROM)),
         "Выбор": st.column_config.CheckboxColumn("Выбор", width="small"),
         "Оценка": st.column_config.TextColumn("Оценка", width="small", alignment="center"),
         "Оценка (звук)": st.column_config.SelectboxColumn("Оценка (звук)", options=["👍", "👎"], width="small", required=False),
         "Подсказка": st.column_config.TextColumn("Подсказка", help="Доп. описание для картинки; русский переводится на английский"),
         "Картинка": st.column_config.LinkColumn("Картинка", display_text=":material/image:", width="small"),
         "Озвучка": st.column_config.LinkColumn("Озвучка", display_text=":material/play_circle:", width="small"),
         "Ударение": st.column_config.NumberColumn("Ударение", min_value=1, max_value=20, step=1, width="small",
                                                   help="Номер ударного слога (по гласным); пусто — авто. Затем «Сгенерировать звук»")},
        pinned=("Выбор", "Решение", "id"), host=gear_col)
    if sort:
        df = df.sort_values(sort[0], ascending=sort[1], kind="stable")
    edited = tbl.data_editor(
        df, key=key, hide_index=True, use_container_width=True, column_order=order, column_config=config,
        disabled=["id", "Категория", "Возраст", "Приоритет", "Картинка", "Оценка", "Озвучка", "Флаги"])
    _ai = {"👍": "up", "👎": "down"}
    for wid, o, n in zip(df["id"], df["Оценка (звук)"], edited.set_index(df.index)["Оценка (звук)"]):
        o, n = _ai.get(o, ""), _ai.get(n, "")
        if o != n:
            set_avote(root, wid, n)
    with cap_col:
        _tb_pager(page, pages, len(sel), len(rows))
    import streamlit.components.v1 as _cv
    amap = {}
    for r in chunk:
        if r["audio"]:
            k = f"{'ru' if 'ru' in r['audio'] else r['audio'][0]}/{r['id']}"
            f = root / "audio" / f"{k}.mp3"
            if f.is_file():
                amap[k] = _b64(str(f), f.stat().st_mtime)
    _cv.html("<script>(function(){const p=window.parent;p.__amap=" + json.dumps(amap) + ";" + _APLAY_JS + "})();</script>", height=0)
    sel_set.difference_update(vis_ids)
    sel_set.update(edited.loc[edited["Выбор"], "id"].tolist())
    sel_set.intersection_update(r["id"] for r in sel)  # выбор невидимых (отфильтрованных) строк не живёт
    st.session_state.setdefault("tb_prev", True)  # Просмотр включён по умолчанию
    _by = {r["id"]: r for r in chunk}
    prev_rows = [_by[i] for i in df["id"] if _by[i]["img"]][:PREV_MAX]  # порядок как в таблице
    picked = [r["id"] for r in sel if r["id"] in sel_set]
    with sel_slot:
        st.session_state["tb_selall"] = bool(vis_ids) and all(i in sel_set for i in vis_ids)
        with st.container(key="cmp_selall"):
            sc1, _sc2 = st.columns(2, vertical_alignment="center")
            sc1.checkbox(f"Выбрать все ({len(vis_ids)})", key="tb_selall", on_change=_selall_cb)
    marked = [r["id"] for r in prev_rows if st.session_state.get(f"pv_{r['id']}")] if st.session_state.get("tb_prev") else []
    targets = marked or picked
    with st.container(key="actions_words"):
        act_cols = st.columns([2, 1, 1, 1, 1, 1])
        act_cols[0].markdown(f"<div style='display:flex;align-items:center;height:100%;'><span style='font-family:IBM Plex Sans,system-ui,sans-serif;font-size:11px;font-weight:500;color:#596178;line-height:32px;'>✓ ок: {c['ok']} · ✗ удалить: {c['del']} · с правками: {c['edit']} · всего слов: {len(rows)}</span></div>", unsafe_allow_html=True)
        if act_cols[4].button(f"Сгенерировать подсказку ({len(targets)})", disabled=not targets, key="words_vis_btn",
                             help="LLM пишет сцену-подсказку (ru) для выбранных слов; затем правьте и генерируйте картинку"):
            with st.spinner(f"Подсказки: {len(targets)} шт.…"):
                record_feedback(root, load_images_reg(root), {i: dec.get(i, {}).get("hint", "") for i in targets})
                rc, out = _run(root, sys.executable, "scripts/imggen.py", "visual", "--ids", ",".join(targets), "--force")
                vf = root / "registry" / "visual.json"
                vis = json.loads(vf.read_text("utf-8")) if vf.exists() else {}
                for i in targets:
                    if vis.get(i, {}).get("ru"):
                        stage(dec, i, "hint", vis[i]["ru"])
                save_decisions(root, dec)
            st.session_state["tb_selver"] = st.session_state.get("tb_selver", 0) + 1  # новый key -> data_editor перечитает df
            notify.report("success" if rc == 0 else "error", "Подсказки", details=[out[-1500:]])
            st.rerun()
        if _ask("tts", act_cols[5].button(f"Сгенерировать звук ({len(targets)})", disabled=not targets, key="words_tts_btn",
                             help="Озвучка (ru) выбранных слов: Chatterbox, клон голоса; ударение — из колонки «Ударение». "
                                  "Нужен запущенный scripts/tts_server.py (~3–5 с на слово)."), targets, avotes) \
                or st.session_state.pop("_go_tts", False):
            ru_t = dict(zip(edited["id"], edited[lang_label("ru")].fillna("")))
            st_n = dict(zip(edited["id"], edited["Ударение"]))
            items = [{"id": i, "text": ru_t[i], "stress": int(st_n[i]) if st_n[i] == st_n[i] and st_n[i] else None}
                     for i in targets if ru_t.get(i)]
            with st.spinner(f"Озвучка: {len(items)} шт., по очереди…"):
                rc, out = run_tts(items)
            for i in targets:
                set_avote(root, i, "")  # новая озвучка -> старая оценка сброшена
            st.session_state["tb_selver"] = st.session_state.get("tb_selver", 0) + 1
            notify.report("success" if rc == 0 else "error", "Озвучка", details=[out[-1500:]])
            st.rerun()
        act_cols[1].button("Просмотр", key="words_prev_btn", disabled=not prev_rows, on_click=_toggle_prev,
                          type="primary" if st.session_state.get("tb_prev") else "secondary")
        gen_label = (f"Перегенерировать отмеченные ({len(marked)})" if marked
                     else f"Сгенерировать картинку ({len(picked)})")
        if _ask("img", act_cols[2].button(gen_label, disabled=not targets, key="words_gen_btn", help=GEN_HELP), targets, votes) \
                or st.session_state.pop("_go_img", False):
            hints = dict(zip(edited["id"], (edited["Подсказка"].fillna("").str.strip())))
            with st.spinner(f"Генерация: {len(targets)} шт., по очереди…"):
                record_feedback(root, load_images_reg(root), {i: h for i, h in hints.items() if i in targets})
                rc, out = run_imggen(root, targets, hints)
            notify.report("success" if rc == 0 else "error", "Генерация картинок", details=[out[-1500:]])
            st.rerun()
        save = act_cols[3].button("Сохранить в черновик", type="primary", key="words_save_btn")
    cf = st.session_state.get("_cf")
    if cf:
        liked = [i for i in targets if (votes if cf == "img" else avotes).get(i) == "up"]
        if not liked:
            st.session_state.pop("_cf")
        else:
            st.warning(f"У {len(liked)} из {len(targets)} слов стоит 👍 ({'картинка' if cf == 'img' else 'звук'}). "
                       f"Перегенерировать и потерять удачный вариант?")
            y, n, _sp = st.columns([2, 1, 6])
            if y.button("Да, перегенерировать", key="cf_yes", type="primary"):
                st.session_state.pop("_cf")
                st.session_state["_go_" + cf] = True
                st.rerun()
            if n.button("Отмена", key="cf_no"):
                st.session_state.pop("_cf")
                st.rerun()
    if st.session_state.get("tb_prev") and prev_rows:
        _preview(root, prev_rows)
    st.divider()
    _decisions_block(root, dec)
    if not save:
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
        for lab, fld in (("Заметка", "note"), ("Подсказка", "hint")):
            nv, ov = (new[lab] or "").strip(), (old[lab] or "").strip()
            if nv != ov:
                stage(dec, wid, fld, nv, r[fld])
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
    _tts_settings(root)

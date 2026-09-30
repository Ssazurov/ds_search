"""Чеклист публикации пересказа (digest) — логика UI без Streamlit (ds_search#421).

Публикация пересказа блокируется, пока все пункты не пройдены:
ссылка на источник, цитат ≤ 2 (каждая ≤ 25 слов), нет серии ≥ 8 слов
из оригинала, выбраны направление и категория.
"""
from __future__ import annotations

from . import overlap


def _has_http_source(item: dict) -> bool:
    from .publish import effective_source_url
    return effective_source_url(item).lower().startswith(("http://", "https://"))


def evaluate(item: dict, source_text: str | None = None) -> dict:
    """{overlap: dict|None, checks: [{label, ok, hint}], ok: bool}.
    Оригинал — source_text или item['source_text']; без него серия не
    проверяема, пункт считается непройденным."""
    src = source_text if source_text is not None else (item.get("source_text") or "")
    quotes = item.get("quotes") or []
    ov = overlap.check_overlap(src, item.get("body_md") or "", quotes) if src.strip() else None

    quote_warn = overlap.check_quotes(quotes)
    if ov is None:
        run_ok, run_hint = False, "нет текста оригинала — сравнить нельзя"
    else:
        run_ok = ov["max_run"] < overlap.MAX_RUN_WORDS
        run_hint = f"макс. серия {ov['max_run']} слов (порог {overlap.MAX_RUN_WORDS})"
    checks = [
        {"label": "Ссылка на источник (http/https)", "ok": _has_http_source(item), "hint": ""},
        {"label": f"Цитат ≤ {overlap.MAX_QUOTES}", "ok": not quote_warn, "hint": "; ".join(quote_warn)},
        {"label": f"Нет серии ≥ {overlap.MAX_RUN_WORDS} слов из оригинала", "ok": run_ok, "hint": run_hint},
        {"label": "Направление и категория выбраны",
         "ok": bool(item.get("direction")) and bool(item.get("category")), "hint": ""},
    ]
    return {"overlap": ov, "checks": checks, "ok": all(c["ok"] for c in checks)}


def blockers(item: dict) -> list[str]:
    """Метки непройденных пунктов; [] — можно публиковать. Для news всегда []."""
    if item.get("format") != "digest":
        return []
    return [c["label"] for c in evaluate(item)["checks"] if not c["ok"]]

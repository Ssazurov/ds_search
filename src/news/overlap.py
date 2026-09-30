"""Проверка пересказа (digest) на близость к оригиналу (ds_search#420, ADR-0024).

Эвристика, не юридическая гарантия: ищем самую длинную дословную серию слов,
общую с источником, и долю n-грамм пересказа, встречающихся в источнике.
Цитаты в «ёлочках» из проверки исключаются — они контролируются отдельно
(число и длина, check_quotes).
"""
from __future__ import annotations

import re

MAX_RUN_WORDS = 8        # серия дословно совпадающих слов ≥ порога — предупреждение
MAX_RATIO = 0.15         # доля совпадающих n-грамм пересказа с источником
NGRAM = 5
MAX_QUOTES = 2
MAX_QUOTE_WORDS = 25

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_QUOTE_RE = re.compile(r"«[^«»]*»")


def _words(text: str) -> list[str]:
    return [w.lower().replace("ё", "е") for w in _WORD_RE.findall(text or "")]


def strip_quotes(text: str) -> str:
    """Убрать фрагменты в «ёлочках» (контролируемые цитаты)."""
    return _QUOTE_RE.sub(" ", text or "")


def _grams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def longest_shared_run(source: list[str], draft: list[str]) -> int:
    """Длина самой длинной общей непрерывной серии слов (бинарный поиск по k)."""
    lo, hi = 0, min(len(source), len(draft))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _grams(source, mid) & _grams(draft, mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


def overlap_ratio(source: list[str], draft: list[str], n: int = NGRAM) -> float:
    draft_grams = _grams(draft, n)
    if not draft_grams:
        return 0.0
    return len(draft_grams & _grams(source, n)) / len(draft_grams)


def check_quotes(quotes: list[str] | None) -> list[str]:
    warnings: list[str] = []
    quotes = quotes or []
    if len(quotes) > MAX_QUOTES:
        warnings.append(f"цитат {len(quotes)} > {MAX_QUOTES}")
    for q in quotes:
        n = len(_words(q))
        if n > MAX_QUOTE_WORDS:
            warnings.append(f"цитата {n} слов > {MAX_QUOTE_WORDS}")
    return warnings


def check_overlap(
    source_text: str, draft_text: str, quotes: list[str] | None = None,
    max_run: int = MAX_RUN_WORDS, max_ratio: float = MAX_RATIO,
) -> dict:
    """{max_run, ratio, ok, warnings}. ok=False — публиковать не рекомендуется."""
    src = _words(source_text)
    dr = _words(strip_quotes(draft_text))
    run = longest_shared_run(src, dr)
    ratio = round(overlap_ratio(src, dr), 4)
    warnings = check_quotes(quotes)
    if run >= max_run:
        warnings.append(f"дословная серия {run} слов ≥ {max_run}")
    if ratio > max_ratio:
        warnings.append(f"перекрытие {ratio:.0%} > {max_ratio:.0%}")
    return {"max_run": run, "ratio": ratio, "ok": not warnings, "warnings": warnings}


def matched_spans(text: str, other: str, n: int = NGRAM, skip_quotes: bool = False) -> list[tuple[int, int]]:
    """Диапазоны символов text, слова которых входят в n-грамму, общую с other.
    skip_quotes — не подсвечивать «ёлочки» (цитаты контролируются отдельно)."""
    toks = [(m.start(), m.end(), m.group().lower().replace("ё", "е")) for m in _WORD_RE.finditer(text or "")]
    words = [t[2] for t in toks]
    other_grams = _grams(_words(other), n)
    covered = [False] * len(toks)
    for i in range(len(words) - n + 1):
        if tuple(words[i:i + n]) in other_grams:
            for j in range(i, i + n):
                covered[j] = True
    if skip_quotes:
        qspans = [m.span() for m in _QUOTE_RE.finditer(text or "")]
        for j, (s, e, _) in enumerate(toks):
            if any(qs <= s and e <= qe for qs, qe in qspans):
                covered[j] = False
    spans: list[tuple[int, int]] = []
    for j, (s, e, _) in enumerate(toks):
        if not covered[j]:
            continue
        if spans and j > 0 and covered[j - 1]:
            spans[-1] = (spans[-1][0], e)
        else:
            spans.append((s, e))
    return spans


def highlight_html(text: str, other: str, n: int = NGRAM, skip_quotes: bool = False) -> str:
    """HTML-экранированный text с <mark> на фрагментах, совпадающих с other."""
    from html import escape
    text = text or ""
    out, pos = [], 0
    for s, e in matched_spans(text, other, n, skip_quotes):
        out.append(escape(text[pos:s]))
        out.append(f"<mark>{escape(text[s:e])}</mark>")
        pos = e
    out.append(escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")

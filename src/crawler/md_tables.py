"""issue #460: схлопывание markdown-таблиц с многострочными ячейками (html2text).

html2text иногда выдаёт строку таблицы так:
    |
    <текст ячейки>
     |
    <текст ячейки>
     |
Такая таблица не рендерится. Функция склеивает строку в одну: "| a | b |".
Модуль без внешних зависимостей (используется и краулером, и scripts/migrate_fix_tables.py).
"""
import re

_SEP = re.compile(r'^\|(\s*:?-{3,}:?\s*\|)+\s*$')
_MAX_ROW_LINES = 400


def _collapse_row(buf: list[str], cols: int = 0) -> str | None:
    parts = " ".join(buf).split("|")
    if len(parts) < 3 or parts[0].strip() or parts[-1].strip():
        return None
    cells = [" ".join(p.split()) or " " for p in parts[1:-1]]
    cells += [" "] * (cols - len(cells))  # colspan/rowspan: добиваем пустыми
    return "| " + " | ".join(cells) + " |"


def collapse_multiline_tables(markdown: str) -> str:
    lines = markdown.split("\n")
    out: list[str] = []
    n = None          # число колонок текущей таблицы
    broken = False    # таблица содержала многострочные строки
    i = 0
    while i < len(lines):
        ln = lines[i]
        if broken and not ln.strip():
            # пустые строки внутри «сломанной» таблицы убираем
            k = i
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k < len(lines) and lines[k].startswith("|"):
                i = k
                continue
        if not ln.startswith("|"):
            if ln.strip():
                n = None
            if broken and ln.strip():
                if out and out[-1] != "":
                    out.append("")
                broken = False
            elif broken:
                broken = False
            out.append(ln)
            i += 1
            continue
        s = ln.rstrip()
        if _SEP.match(s):
            n = s.count("|") - 1
            out.append(s)
            i += 1
            continue
        if len(s) > 1 and s.endswith("|"):
            out.append(s)
            i += 1
            continue
        # многострочная строка: определяем число колонок
        cols = n
        if cols is None:
            for j in range(i + 1, min(i + _MAX_ROW_LINES, len(lines))):
                t = lines[j].rstrip()
                if _SEP.match(t):
                    cols = t.count("|") - 1
                    break
        row = None
        j = i + 1
        if cols:
            buf, pipes = [ln], ln.count("|")
            while pipes < cols + 1 and j < len(lines) and j - i < _MAX_ROW_LINES:
                if lines[j].startswith("|"):
                    break
                pipes += lines[j].count("|")
                buf.append(lines[j])
                j += 1
            if pipes == cols + 1:
                row = _collapse_row(buf)
            elif j < len(lines) and lines[j].startswith("|") and pipes >= 2:
                row = _collapse_row(buf, cols)  # следующая строка началась раньше (colspan)
        if row is None:
            out.append(ln)
            i += 1
            continue
        out.append(row)
        broken = True
        i = j
    # html2text: "<b>Текст</b> <b>A</b>" -> "**Текст****A**" внутри таблиц
    out = [l.replace("****", " ") if l.startswith("|") and "****" in l else l for l in out]
    return "\n".join(out)



# html2text: соседние <b>a</b><b>b</b> -> "**a****b**" (и "_a_****_b_" для <b><i>).
_ADJ_EMPH_RE = re.compile(r'(?P<l>[^\s*_])(?P<u1>_?)\*\*\*\*(?P<u2>_?)(?P<r>[^\s*_])')
_CYR_RE = re.compile(r'[А-Яа-яЁё]')


def _adj_repl(m):
    l, u1, u2, r = m.group('l'), m.group('u1'), m.group('u2'), m.group('r')
    if bool(u1) != bool(u2):
        return m.group(0)  # несбалансированный курсив — не трогаем
    if r in ',.;:!?)»…':
        sep = ''
    elif l.isalpha() and r.isalpha() and not (_CYR_RE.match(l) or _CYR_RE.match(r)):
        sep = ''  # латиница: слово разрезано тегами (And****roid)
    else:
        sep = ' '
    return l + sep + r


def merge_adjacent_emphasis(markdown: str) -> str:
    """Склеивает соседние bold-спаны: '**Новая жизнь****, любовь**' -> '**Новая жизнь, любовь**'."""
    if '****' not in markdown:
        return markdown
    return _ADJ_EMPH_RE.sub(_adj_repl, markdown)

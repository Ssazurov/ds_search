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
    s = m.string
    pre = s[m.start('l') - 1] if m.start('l') > 0 else ''
    post = s[m.end('r')] if m.end('r') < len(s) else ''
    if r in ',.;:!?)»…':
        sep = ''
    elif _CYR_RE.match(l) and _CYR_RE.match(r) and (
        (l.isupper() and not pre.isalpha())  # «М****огли»: заглавная буква отрезана от слова
        or (r in 'юыьъйэ' and not post.isalpha())  # «поняти****ю»: хвост слова
    ):
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
    out = _ADJ_EMPH_RE.sub(_adj_repl, markdown)
    # остаток: "****" рядом с пробелом ("Натальи**** Сергеевны") — просто убираем
    return _ADJ_SPACE_RE.sub('', out)


_SINGLE_US_RE = re.compile(r'(?<!_)_(?!_)')
_US_PROTECT_RE = re.compile(r'!\[(?:\\.|[^\]\\])*\](?:\((?:\\.|[^)\\])*\))?|\]\((?:\\.|[^)\\])*\)|https?://[^\s)]+|<[^>]+>')


def strip_orphaned_underscore_emphasis(markdown: str) -> str:
    """issue #562: <em>/<i> вокруг картинки/нескольких <p> даёт '_' в разных
    абзацах; CommonMark emphasis абзацы не пересекает -> непарные '_' видны
    как символ. В пределах абзаца парим одиночные '_' слева направо, непарные
    удаляем."""
    out = []
    for para in re.split(r'(\n{2,})', markdown):
        if para.strip('\n') == '' or '_' not in para:
            out.append(para)
            continue
        drop = set()
        open_pos = None
        protected = set()  # '_' внутри URL/ссылок/картинок не трогаем
        for pm in _US_PROTECT_RE.finditer(para):
            protected.update(range(pm.start(), pm.end()))
        for m in _SINGLE_US_RE.finditer(para):
            p = m.start()
            if p in protected:
                continue
            prev = para[p - 1] if p > 0 else ''
            nxt = para[p + 1] if p + 1 < len(para) else ''
            if prev.isalnum() and nxt.isalnum():
                continue  # intraword '_' — не emphasis
            left_flank = nxt != '' and not nxt.isspace()
            right_flank = prev != '' and not prev.isspace()
            if open_pos is None:
                if left_flank:
                    open_pos = p
                else:
                    drop.add(p)
            elif right_flank:
                open_pos = None
            elif left_flank:
                drop.add(open_pos)
                open_pos = p
            else:
                drop.add(p)
        if open_pos is not None:
            drop.add(open_pos)
        if drop:
            para = ''.join(c for i, c in enumerate(para) if i not in drop)
        out.append(para)
    return ''.join(out)


_ADJ_SPACE_RE = re.compile(r'(?<=\S)\*\*\*\*(?=\s)|(?<=\s)\*\*\*\*(?=\S)')
_ADJ_TAG_RE = re.compile(
    r'</(b|strong|i|em)>((?:\s|&nbsp;|\xa0)*)<\1(?:\s[^>]*)?>', re.IGNORECASE
)


def merge_adjacent_inline_tags(html: str) -> str:
    """Склеивает на уровне HTML соседние <b>a</b><b>b</b> (в т.ч. через &nbsp;/пробелы)
    ДО html2text — иначе получаются "**М****огли" и теряются пробелы."""
    prev = None
    while prev != html:
        prev = html
        html = _ADJ_TAG_RE.sub(r'\2', html)
    return html


_NUM_BOLD_WRAP_RE = re.compile(r'^(?P<ind>[ \t]{0,3})\*\*(?P<n>\d{1,3})[.)]\s*(?P<b>[^*\n]+?)\*\*(?P<rest>.*)$')
_NUM_BOLD_NUM_RE = re.compile(r'^(?P<ind>[ \t]{0,3})\*\*(?P<n>\d{1,3})(?:[.)]\*\*|\*\*[.)])[ \t]*(?P<rest>\S.*)$')
_NUM_NODOT_RE = re.compile(r'^(?P<ind>[ \t]{0,3})(?P<n>\d{1,3})[ \t]+(?=\*\*[^\s*])')
_LIST_ITEM_RE = re.compile(r'^[ \t]{0,3}\d{1,3}[.)][ \t]')
_FENCE_RE = re.compile(r'^[ \t]*(```|~~~)')


def normalize_numbered_lists(markdown: str) -> str:
    """issue #566: нумерация списка после html2text приходит в разных видах:
    '1. **A**', '2 **B**' (без точки), '**3. C**' (номер внутри жирного),
    '**4.** D'. Приводим к '<N>. ...' (номер вне bold); перед пунктом N!=1,
    идущим вплотную за абзацем, вставляем пустую строку (иначе CommonMark
    не считает его списком)."""
    if not re.search(r'(?m)^[ \t]{0,3}(\*\*)?\d{1,3}[.)\s*]', markdown):
        return markdown
    out: list[str] = []
    in_fence = False
    for line in markdown.split('\n'):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            m = _NUM_BOLD_WRAP_RE.match(line)
            if m:
                line = f"{m['ind']}{m['n']}. **{m['b'].strip()}**{m['rest']}"
            else:
                m = _NUM_BOLD_NUM_RE.match(line)
                if m:
                    line = f"{m['ind']}{m['n']}. {m['rest']}"
                else:
                    m = _NUM_NODOT_RE.match(line)
                    if m:
                        line = f"{m['ind']}{m['n']}. " + line[m.end():]
            if (_LIST_ITEM_RE.match(line) and not line.lstrip().startswith('1.')
                    and out and out[-1].strip() and not _LIST_ITEM_RE.match(out[-1])
                    and not out[-1].startswith((' ', '\t'))):
                out.append('')
        out.append(line)
    return '\n'.join(out)

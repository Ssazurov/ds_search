#!/usr/bin/env python3
"""Аудит markdown-таблиц в data/raw/**/*.md: ищет сломанные таблицы (issue #460)."""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SEP = re.compile(r'^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*:?-*:?\s*$')
root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw")
problems = defaultdict(list)
files_with_tables = 0

for p in root.rglob("*.md"):
    lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
    has_t = False
    for i, ln in enumerate(lines):
        s = ln.rstrip()
        if SEP.match(s) and "|" in s and "-" in s:
            has_t = True
            n = s.strip().strip("|").count("|") + 1
            # шапка
            if i == 0 or not lines[i - 1].lstrip().startswith("|"):
                problems["sep_without_header"].append((p, i + 1))
            else:
                h = lines[i - 1].rstrip()
                if not h.endswith("|"):
                    problems["header_not_closed"].append((p, i + 1))
                elif h.strip().strip("|").count("|") + 1 != n:
                    problems["header_cols_mismatch"].append((p, i + 1))
            # тело
            j = i + 1
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                r = lines[j].rstrip()
                if not r.endswith("|") or len(r) < 2:
                    problems["row_not_closed"].append((p, j + 1))
                elif r.strip().strip("|").count("|") + 1 != n and not SEP.match(r):
                    problems["row_cols_mismatch"].append((p, j + 1))
                j += 1
            if j == i + 1:
                problems["no_body_rows"].append((p, i + 1))
        if re.match(r'^\s*\|\s*$', ln):
            problems["lone_pipe_line"].append((p, i + 1))
        if re.search(r'\*{4,}', s) and s.lstrip().startswith("|"):
            problems["bold_artifact_****"].append((p, i + 1))
        if re.match(r'^\|.*\|\s*$', s) and not SEP.match(s):
            # строка таблицы без шапки/сепаратора рядом
            prev = lines[i - 1] if i else ""
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not prev.lstrip().startswith("|") and not (nxt.lstrip().startswith("|")):
                problems["orphan_row"].append((p, i + 1))
    if has_t:
        files_with_tables += 1

print(f"files with tables: {files_with_tables}")
for k, v in sorted(problems.items(), key=lambda kv: -len(kv[1])):
    files = Counter(str(x[0].relative_to(root)) for x in v)
    print(f"\n## {k}: {len(v)} in {len(files)} files")
    for f, c in files.most_common(8):
        first = next(l for pp, l in v if str(pp.relative_to(root)) == f)
        print(f"  {c:4d}  {f}:{first}")

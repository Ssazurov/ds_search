#!/usr/bin/env python3
"""Миграция data/raw/**/*.md: склейка соседних bold-спанов (**a****b**). --dry-run для просмотра."""
import sys, json, importlib.util
from datetime import datetime
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    'md_tables', Path(__file__).parent.parent / 'src' / 'crawler' / 'md_tables.py')
_mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mt)

root = Path(__file__).parent.parent / 'data' / 'raw'
dry = '--dry-run' in sys.argv
n = 0
for p in root.rglob('*.md'):
    s = p.read_text(encoding='utf-8')
    if '****' not in s:
        continue
    t = _mt.merge_adjacent_emphasis(s)
    if t == s:
        continue
    n += 1
    print(('DRY ' if dry else 'FIX ') + str(p.relative_to(root)))
    if dry:
        continue
    p.write_text(t, encoding='utf-8')
    j = p.with_suffix('.json')
    if j.exists():
        d = json.loads(j.read_text(encoding='utf-8'))
        d['modified_at'] = datetime.utcnow().isoformat() + 'Z'
        j.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
print('files:', n)

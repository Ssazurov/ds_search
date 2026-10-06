"""One-off: чинит '****' (битые bold-спаны) в уже скачанных data/raw/**/*.md.
Запуск: .venv/bin/python3 scripts/fix_emphasis.py [--dry]"""
import sys
from pathlib import Path

from src.crawler.md_tables import merge_adjacent_emphasis

dry = '--dry' in sys.argv
changed = 0
for p in Path('data/raw').rglob('*.md'):
    t = p.read_text(encoding='utf-8')
    n = merge_adjacent_emphasis(t)
    if n != t:
        changed += 1
        if not dry:
            p.write_text(n, encoding='utf-8')
print(('would change' if dry else 'changed'), changed)

"""Бэкфилл license/attribution в уже собранных data/raw/<source>/*.json
по текущему состоянию config/licenses.yaml (follow-up issue, вне scope #5).
Разовый скрипт, не часть постоянного пайплайна.

Использование: python3 scripts/backfill_license.py <source>
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main(source: str) -> None:
    registry = yaml.safe_load((ROOT / 'config' / 'licenses.yaml').read_text(encoding='utf-8')) or {}
    src_dir = ROOT / 'data' / 'raw' / source
    files = sorted(src_dir.glob('*.json'))
    updated = 0
    for jp in files:
        meta = json.loads(jp.read_text(encoding='utf-8'))
        entry = registry.get(meta['source_domain'])
        if entry is None:
            continue
        old = meta.get('license')
        meta['license'] = entry['status']
        tmpl = entry.get('attribution_template')
        if tmpl:
            meta['attribution'] = tmpl.format(title=meta['title'], source_url=meta['source_url'])
        if old != meta['license']:
            updated += 1
        jp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{source}: обработано {len(files)}, изменено license {updated}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python3 scripts/backfill_license.py <source>')
    main(sys.argv[1])

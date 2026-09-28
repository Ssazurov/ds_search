"""Бэкфилл title (без суффикса site_name) и attribution (шаблон домена из реестра GAR) — issue #347.
Использование: python3 scripts/backfill_title_attribution.py <source> [--dry]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.license.registry_store import load_registry
from src.metadata.meta_extract import strip_site_suffix

ROOT = Path(__file__).resolve().parents[1]


def main(source: str, dry: bool) -> None:
    registry = load_registry()
    changed = 0
    for jp in sorted((ROOT / "data" / "raw" / source).glob("*.json")):
        meta = json.loads(jp.read_text(encoding="utf-8"))
        new = dict(meta)
        entry = registry.get(meta.get("source_domain")) or {}
        new["title"] = strip_site_suffix(meta.get("title"), entry.get("site_name"))
        tmpl = entry.get("attribution_template")
        if tmpl:
            new["attribution"] = tmpl.format(
                title=new.get("title", ""), source_url=meta["source_url"], domain=meta["source_domain"],
            )
        if new != meta:
            changed += 1
            print(jp.name, "|", meta.get("title"), "->", new.get("title"), "|", new.get("attribution"))
            if not dry:
                jp.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{source}: изменено {changed}{' (dry)' if dry else ''}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: backfill_title_attribution.py <source> [--dry]")
    main(sys.argv[1], "--dry" in sys.argv)

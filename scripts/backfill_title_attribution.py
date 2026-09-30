"""Бэкфилл title (без суффикса site_name) и attribution (шаблон домена из реестра GAR)
— issues #347, #395, #396.
site_name: поле реестра, иначе выводится из attribution_template (derive_site_name).
Использование: python3 scripts/backfill_title_attribution.py <source>|--all [--dry]
Изменённые файлы пишутся в data/backfill_changed.txt (для перезагрузки в GAR).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.license.checker import derive_site_name
from src.license.registry_store import load_registry
from src.metadata.meta_extract import strip_site_suffix

ROOT = Path(__file__).resolve().parents[1]


def main(source: str, dry: bool) -> None:
    registry = load_registry()
    base = ROOT / "data" / "raw"
    dirs = sorted(p for p in base.iterdir() if p.is_dir()) if source == "--all" else [base / source]
    changed_paths: list[str] = []
    for d in dirs:
        for jp in sorted(d.glob("*.json")):
            try:
                meta = json.loads(jp.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not isinstance(meta, dict):
                continue
            entry = registry.get(meta.get("source_domain")) or {}
            site = entry.get("site_name") or derive_site_name(entry.get("attribution_template"))
            new = dict(meta)
            new["title"] = strip_site_suffix(meta.get("title"), site)
            if new["title"] == meta.get("title"):
                continue  # #396: трогаем только файлы с суффиксом в title
            tmpl = entry.get("attribution_template")
            if tmpl and meta.get("source_url"):
                new["attribution"] = tmpl.format(
                    title=new.get("title", ""), source_url=meta["source_url"], domain=meta["source_domain"],
                )
            if new != meta:
                changed_paths.append(str(jp))
                print(jp.relative_to(base), "|", meta.get("title"), "->", new.get("title"))
                if not dry:
                    jp.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
                    if "--gar" in sys.argv and new.get("gar_document_id"):
                        from src.gar_ingest.client import GarIngestClient, load_settings
                        with GarIngestClient(load_settings()) as c:
                            c.patch_document_metadata(
                                new["gar_document_id"],
                                {"title": new["title"], "attribution": new.get("attribution")},
                            )
                        print("  GAR patched", new["gar_document_id"])
    if not dry:
        (ROOT / "data" / "backfill_changed.txt").write_text("\n".join(changed_paths), encoding="utf-8")
    print(f"изменено {len(changed_paths)}{' (dry)' if dry else ''}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: backfill_title_attribution.py <source>|--all [--dry]")
    main(sys.argv[1], "--dry" in sys.argv)

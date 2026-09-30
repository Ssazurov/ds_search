"""Свести папки data/raw/www.<домен>/ к каноничным <домен>/ (issue #400).

Также нормализует source_domain в sidecar-JSON (без www.). Дубликаты (тот же doc_id и source_url)
удаляются. Usage: python3 scripts/merge_www_folders.py [--dry-run]
"""
import json
import shutil
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
INTERNAL = {"glossary", "glossary_items", "links", "links_items", "science"}


def fix_cp(old_cp: str, dest: Path) -> str:
    if not old_cp:
        return old_cp
    p = Path(old_cp)
    if p.parent.parent.name == "raw":
        return str(p.parent.parent / dest.parent.name / dest.name)
    return str(dest)  # битый путь (без raw/) -> реальный хост-путь


def main(dry: bool) -> None:
    moved = dropped = fixed = 0
    for d in sorted(RAW.iterdir()):
        if not d.is_dir() or d.name in INTERNAL:
            continue
        canon = d.name.removeprefix("www.")
        for jp in sorted(d.glob("*.json")):
            try:
                meta = json.loads(jp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            dest_dir = RAW / canon
            dest = dest_dir / jp.name
            exts = [e for e in (".md", ".pdf") if jp.with_suffix(e).exists()]
            if dest != jp and dest.exists():
                other = json.loads(dest.read_text(encoding="utf-8"))
                if other.get("source_url") == meta.get("source_url"):
                    print(f"DUP drop: {jp}")
                    if not dry:
                        for e in [".json", *exts]:
                            jp.with_suffix(e).unlink(missing_ok=True)
                    dropped += 1
                else:
                    print(f"COLLISION skip: {jp}")
                continue
            new_dom = (meta.get("source_domain") or canon).removeprefix("www.")
            changed = new_dom != meta.get("source_domain") or dest != jp
            meta["source_domain"] = new_dom
            old_cp = meta.get("content_path") or ""
            fname = Path(old_cp).name if old_cp else f"{jp.stem}{exts[0] if exts else '.md'}"
            meta["content_path"] = fix_cp(old_cp, dest_dir / fname)
            changed = changed or meta["content_path"] != old_cp
            if not changed:
                continue
            print(("MOVE " if dest != jp else "FIX  ") + f"{d.name}/{jp.name} -> {canon}")
            if dry:
                continue
            dest_dir.mkdir(exist_ok=True)
            for e in exts:
                if dest != jp:
                    shutil.move(str(jp.with_suffix(e)), str(dest_dir / f"{jp.stem}{e}"))
            if dest != jp:
                jp.unlink()
            dest.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            moved += dest != jp
            fixed += changed
        if not dry and d.name != canon and d.exists() and not any(d.iterdir()):
            d.rmdir()
            print(f"RMDIR {d}")
    print(f"moved={moved} dropped={dropped} fixed={fixed}")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)

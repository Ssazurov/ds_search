"""Миграция файлов из нестандартных папок в data/raw/<domain>/.

Переносит JSON+MD файлы из папок manual/, downsideup/, family_support/,
ПОДДЕРЖКА СЕМЬИ/, basic/, _missing_content/ в соответствующие папки доменов.
Пропускает внутренние папки (glossary, links, science).

Usage: python3 scripts/migrate_raw_folders.py [--dry-run]
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

# Папки, которые нужно мигрировать (не внутренние)
MIGRATABLE_DIRS = {"manual", "downsideup", "family_support", "ПОДДЕРЖКА СЕМЬИ", "basic", "_missing_content"}


def main(dry_run: bool = False) -> None:
    moved = 0
    skipped = 0

    for dir_name in MIGRATABLE_DIRS:
        src_dir = RAW_DIR / dir_name
        if not src_dir.exists():
            continue

        for json_path in sorted(src_dir.rglob("*.json")):
            try:
                meta = json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print(f"SKIP (bad json): {json_path}")
                skipped += 1
                continue

            domain = meta.get("source_domain", "")
            if not domain:
                print(f"SKIP (no domain): {json_path}")
                skipped += 1
                continue

            dest_dir = RAW_DIR / domain
            dest_dir.mkdir(parents=True, exist_ok=True)

            doc_id = json_path.stem
            dest_json = dest_dir / f"{doc_id}.json"

            # Check for collision
            if dest_json.exists():
                print(f"SKIP (collision): {json_path} -> {dest_json}")
                skipped += 1
                continue

            # Update content_path: сохраняем исходный префикс (host или /app), меняем только папку
            old_cp = meta.get("content_path") or ""
            ext = Path(old_cp).suffix or (".pdf" if json_path.with_suffix(".pdf").exists() else ".md")
            if old_cp:
                meta["content_path"] = str(Path(old_cp).parent.parent / domain / f"{doc_id}{ext}")

            if dry_run:
                print(f"DRY-RUN: {json_path.parent.name}/{json_path.name} -> {domain}/{json_path.name}")
                moved += 1
                continue

            # Move files
            for ext_ in (".md", ".pdf"):
                src_f = json_path.with_suffix(ext_)
                if src_f.exists():
                    shutil.move(str(src_f), str(dest_dir / f"{doc_id}{ext_}"))
            shutil.move(str(json_path), str(dest_json))

            # Write updated JSON
            dest_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"MOVED: {json_path.parent.name}/{json_path.name} -> {domain}/{json_path.name}")
            moved += 1

    # Clean up empty directories (bottom-up to handle nested dirs)
    for dir_name in sorted(MIGRATABLE_DIRS, key=len, reverse=True):
        src_dir = RAW_DIR / dir_name
        if src_dir.exists():
            # Remove empty subdirectories first
            for sub in sorted(src_dir.rglob("*"), reverse=True):
                if sub.is_dir() and not any(sub.iterdir()):
                    if not dry_run:
                        sub.rmdir()
                    print(f"REMOVED empty subdir: {sub}")
            # Remove the dir itself if empty
            if not any(src_dir.iterdir()):
                if not dry_run:
                    src_dir.rmdir()
                print(f"REMOVED empty dir: {src_dir}")

    print(f"\nMoved: {moved}, Skipped: {skipped}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)

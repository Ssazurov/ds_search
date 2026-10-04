"""Миграция файлов из неверных папок в data/raw/<домен>/ (issue #400).

Папка для каждого документа определяется по его source_domain (resolve_target_folder),
а не по жёстко заданному списку "неправильных" директорий. Файлы с source_domain
"ds_search" (внутренние, напр. glossary) не трогаются.

Usage: python3 scripts/migrate_raw_folders.py [--dry-run]
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crawler.slug import norm_domain, transliterate  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"


def resolve_target_folder(domain: str, raw_dir: Path) -> Path:
    """Папка для документа по его source_domain: ascii-домены как есть, остальные — транслит+slug."""
    norm = norm_domain(domain)
    if norm.isascii():
        return raw_dir / norm
    safe = re.sub(r"[^a-z0-9]+", "-", transliterate(norm)).strip("-")
    return raw_dir / safe


def scan_wrong_folders(raw_dir: Path) -> list[tuple[Path, dict, Path]]:
    """Находит JSON-файлы не в своей домен-папке. Возвращает (json_path, meta, target_dir)."""
    migrations: list[tuple[Path, dict, Path]] = []
    for json_path in sorted(raw_dir.rglob("*.json")):
        try:
            meta = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        domain = meta.get("source_domain", "")
        if not domain or domain == "ds_search":
            continue

        target_dir = resolve_target_folder(domain, raw_dir)
        if json_path.parent != target_dir:
            migrations.append((json_path, meta, target_dir))
    return migrations


def main(dry_run: bool = False) -> None:
    moved = 0
    skipped = 0
    touched_dirs: set[Path] = set()

    for json_path, meta, dest_dir in scan_wrong_folders(RAW_DIR):
        doc_id = json_path.stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_json = dest_dir / f"{doc_id}.json"

        if dest_json.exists():
            print(f"SKIP (collision): {json_path} -> {dest_json}")
            skipped += 1
            continue

        old_cp = meta.get("content_path") or ""
        ext = Path(old_cp).suffix or (".pdf" if json_path.with_suffix(".pdf").exists() else ".md")
        if old_cp:
            meta["content_path"] = str(Path(old_cp).parent.parent / dest_dir.name / f"{doc_id}{ext}")

        if dry_run:
            print(f"DRY-RUN: {json_path.parent.name}/{json_path.name} -> {dest_dir.name}/{json_path.name}")
            moved += 1
            continue

        touched_dirs.add(json_path.parent)
        for ext_ in (".md", ".pdf"):
            src_f = json_path.with_suffix(ext_)
            if src_f.exists():
                shutil.move(str(src_f), str(dest_dir / f"{doc_id}{ext_}"))
        shutil.move(str(json_path), str(dest_json))
        dest_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"MOVED: {json_path.parent.name}/{json_path.name} -> {dest_dir.name}/{json_path.name}")
        moved += 1

    # Чистим опустевшие директории снизу вверх
    for d in sorted(touched_dirs, key=lambda p: len(p.parts), reverse=True):
        while d != RAW_DIR and d.exists() and not any(d.iterdir()):
            empty = d
            d = d.parent
            empty.rmdir()
            print(f"REMOVED empty dir: {empty}")

    print(f"\nMoved: {moved}, Skipped: {skipped}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)

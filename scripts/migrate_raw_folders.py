#!/usr/bin/env python3
"""Backfill: перенести файлы из data/raw/manual/ и других неправильных папок в папки источников.

Issue #400: после изменений в manual_add.py (issue #388), ручное скачивание использует
папку домена из SOURCES (например data/raw/foma.ru/), а не data/raw/manual/.
Старые файлы могут остаться в неправильных папках.

Логика:
1. Находим все JSON-файлы в нестандартных папках (glossary_items, links_items, manual, etc.)
2. Определяем правильную папку по source_domain из JSON
3. Переносим файлы в правильные папки
4. Обновляем content_path в JSON при необходимости

Usage:
    python scripts/migrate_raw_folders.py --dry-run  # просмотр без изменений
    python scripts/migrate_raw_folders.py            # выполнить миграцию
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse

# Импортируем конфиг и утилиты
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crawler.config import SOURCES
from crawler.slug import domain_dirname, norm_domain

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"

# Папки, которые считаются "неправильными" и требуют миграции
WRONG_FOLDERS = {
    "manual",
    "glossary",
    "glossary_items",
    "links",
    "links_items",
    "science",
}

# Правильные папки - это домены из SOURCES или папки, соответствующие доменам
CORRECT_FOLDERS = {cfg.domain for cfg in SOURCES.values()}


def resolve_target_folder(source_domain: str, data_root: Path) -> Path:
    """Определить правильную папку для файла по source_domain.
    
    Логика:
    1. Если домен есть в SOURCES -> используем cfg.domain
    2. Иначе используем domain_dirname(source_domain)
    3. Для IDN (кириллических) доменов применяем транслитерацию перед domain_dirname
    """
    # Нормализуем домен
    domain = norm_domain(source_domain)
    
    # Ищем в SOURCES
    cfg = next((c for c in SOURCES.values() if c.domain == domain), None)
    if cfg is not None:
        return data_root / cfg.domain
    
    # Для IDN (кириллических) доменов транслитерируем весь домен
    if any(ord(c) > 127 for c in domain):
        from crawler.slug import slugify
        folder_name = slugify(domain) or "unknown"
    else:
        # Иначе используем domain_dirname
        folder_name = domain_dirname(domain)
    
    return data_root / folder_name


def scan_wrong_folders(data_root: Path) -> list[tuple[Path, dict, Path]]:
    """Сканирует неправильные папки и возвращает список (json_path, json_data, target_folder).
    
    Returns:
        List of (source_json_path, json_content, target_folder_path)
    """
    migrations = []
    
    for folder_name in WRONG_FOLDERS:
        folder = data_root / folder_name
        if not folder.exists():
            continue
            
        for json_path in folder.glob("*.json"):
            try:
                with json_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                
                source_domain = data.get("source_domain", "")
                if not source_domain:
                    print(f"⚠️  {json_path.relative_to(data_root)}: нет source_domain, пропускаем")
                    continue
                
                # Специальный случай: source_domain="ds_search" - это внутренние данные
                if source_domain == "ds_search":
                    print(f"ℹ️  {json_path.relative_to(data_root)}: ds_search (internal), пропускаем")
                    continue
                
                target_folder = resolve_target_folder(source_domain, data_root)
                
                # Если файл уже в правильной папке - пропускаем
                if json_path.parent == target_folder:
                    continue
                
                migrations.append((json_path, data, target_folder))
                
            except Exception as e:
                print(f"❌ Ошибка при чтении {json_path.relative_to(data_root)}: {e}")
    
    return migrations


def migrate_file(
    json_path: Path,
    json_data: dict,
    target_folder: Path,
    data_root: Path,
    dry_run: bool = False,
) -> None:
    """Переносит JSON и соответствующий MD-файл в целевую папку.
    
    Обновляет content_path в JSON, если он указывает на старое расположение.
    """
    rel_json = json_path.relative_to(data_root)
    rel_target = target_folder.relative_to(data_root)
    
    # Определяем целевой путь для JSON
    target_json = target_folder / json_path.name
    
    # Проверяем коллизии
    if target_json.exists() and not dry_run:
        print(f"⚠️  {rel_json} → {rel_target}/{json_path.name}: уже существует, пропускаем")
        return
    
    # Определяем путь к MD-файлу
    content_path = json_data.get("content_path", "")
    md_path = None
    if content_path:
        md_path = Path(content_path)
        if not md_path.is_absolute():
            md_path = data_root / md_path
        elif not md_path.exists():
            # Пробуем относительный путь
            md_path = json_path.with_suffix(".md")
    else:
        md_path = json_path.with_suffix(".md")
    
    # Целевой путь для MD
    target_md = None
    if md_path and md_path.exists():
        target_md = target_folder / md_path.name
    
    # Обновляем content_path в JSON
    new_content_path = None
    if target_md:
        new_content_path = str(target_md.resolve())
        if json_data.get("content_path") != new_content_path:
            json_data["content_path"] = new_content_path
    
    # Вывод
    if md_path and md_path.exists():
        print(f"📦 {rel_json} + {md_path.name} → {rel_target}/")
    else:
        print(f"📄 {rel_json} → {rel_target}/")
    
    if dry_run:
        return
    
    # Создаём целевую папку
    target_folder.mkdir(parents=True, exist_ok=True)
    
    # Переносим MD-файл
    if md_path and md_path.exists():
        shutil.move(str(md_path), str(target_md))
    
    # Сохраняем обновлённый JSON
    with target_json.open("w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    # Удаляем старый JSON
    json_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Переносит файлы из неправильных папок в папки источников"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать, что будет сделано, без фактических изменений",
    )
    args = parser.parse_args()
    
    print(f"🔍 Сканирование {DATA_ROOT}...\n")
    
    migrations = scan_wrong_folders(DATA_ROOT)
    
    if not migrations:
        print("✅ Все файлы уже в правильных папках")
        return
    
    print(f"\n📊 Найдено файлов для переноса: {len(migrations)}\n")
    
    if args.dry_run:
        print("🔍 Режим --dry-run, изменения не будут применены\n")
    
    # Группируем по целевой папке
    by_target = {}
    for json_path, data, target_folder in migrations:
        if target_folder not in by_target:
            by_target[target_folder] = []
        by_target[target_folder].append((json_path, data))
    
    # Выполняем миграцию
    for target_folder, items in sorted(by_target.items()):
        print(f"\n→ {target_folder.relative_to(DATA_ROOT)}/ ({len(items)} файлов)")
        print("─" * 60)
        
        for json_path, data in items:
            migrate_file(json_path, data, target_folder, DATA_ROOT, args.dry_run)
    
    print("\n" + "=" * 60)
    if args.dry_run:
        print(f"✅ Проверка завершена: {len(migrations)} файлов будут перенесены")
    else:
        print(f"✅ Миграция завершена: {len(migrations)} файлов перенесено")


if __name__ == "__main__":
    main()

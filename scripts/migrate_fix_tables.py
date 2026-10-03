#!/usr/bin/env python3
"""Миграция существующих markdown файлов: исправление trailing пробелов в таблицах.

issue #451: применяет _clean_markdown_tables() ко всем data/raw/**/*.md файлам.
"""
import re
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import importlib.util

_spec = importlib.util.spec_from_file_location(
    'md_tables', Path(__file__).parent.parent / 'src' / 'crawler' / 'md_tables.py')
_mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mt)


def _clean_markdown_tables(markdown: str) -> str:
    """issue #447: удаляет trailing пробелы после pipe в markdown-таблицах.
    html2text генерирует "|  \\n" вместо "|\\n", что ломает рендеринг."""
    # Находим строки таблиц (содержат | и заканчиваются пробелами перед \n)
    markdown = _mt.collapse_multiline_tables(markdown)  # issue #460
    return re.sub(r'(\|[^\n]*?) +\n', r'\1\n', markdown)


def has_table(content: str) -> bool:
    """Проверяет, содержит ли markdown таблицы."""
    # Таблица = содержит | и строку-разделитель с дефисами
    return "|" in content and re.search(r'\|[\s\-:]+\|', content) is not None


def needs_cleaning(content: str) -> bool:
    """Проверяет, нужно ли чистить таблицы (есть trailing пробелы после |)."""
    return re.search(r'\|[^\n]*? +\n', content) is not None


def update_sidecar_timestamp(json_path: Path) -> None:
    """Обновляет modified_at в sidecar .json файле."""
    if not json_path.exists():
        return
    
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["modified_at"] = datetime.utcnow().isoformat() + "Z"
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  Не удалось обновить {json_path.name}: {e}")


def migrate_file(md_path: Path, dry_run: bool = False) -> Optional[str]:
    """Мигрирует один .md файл.
    
    Returns:
        - "cleaned" если файл был исправлен
        - "skipped" если изменения не нужны
        - None при ошибке
    """
    try:
        content = md_path.read_text(encoding="utf-8")
    except Exception as e:
        return None  # ошибка чтения
    
    if not has_table(content):
        return "skipped"  # нет таблиц
    
    cleaned = _clean_markdown_tables(content)
    
    if cleaned == content:
        return "skipped"  # функция не изменила контент
    
    if dry_run:
        return "cleaned"
    
    # Пишем исправленный файл
    try:
        md_path.write_text(cleaned, encoding="utf-8")
        # Обновляем sidecar .json
        json_path = md_path.with_suffix(".json")
        update_sidecar_timestamp(json_path)
        return "cleaned"
    except Exception as e:
        print(f"  ❌ Ошибка записи {md_path.relative_to(md_path.parents[3])}: {e}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Исправить trailing пробелы в markdown таблицах")
    parser.add_argument("--dry-run", action="store_true", help="Показать изменения без записи")
    parser.add_argument("--root", type=Path, default=Path(__file__).parent.parent / "data" / "raw",
                        help="Корневая директория для поиска .md файлов")
    args = parser.parse_args()
    
    root: Path = args.root
    if not root.exists():
        print(f"❌ Директория {root} не найдена")
        return 1
    
    print(f"🔍 Сканирование {root}")
    if args.dry_run:
        print("⚠️  DRY RUN режим — файлы не будут изменены\n")
    
    md_files = list(root.rglob("*.md"))
    print(f"Найдено .md файлов: {len(md_files)}")
    
    stats = {"cleaned": 0, "skipped": 0, "errors": 0}
    errors = []
    
    for md_path in md_files:
        rel_path = md_path.relative_to(root)
        result = migrate_file(md_path, dry_run=args.dry_run)
        
        if result == "cleaned":
            stats["cleaned"] += 1
            print(f"✅ {rel_path}")
        elif result == "skipped":
            stats["skipped"] += 1
        else:  # None = error
            stats["errors"] += 1
            errors.append(str(rel_path))
            print(f"❌ {rel_path}")
    
    # Итоговый отчёт
    print(f"\n{'='*60}")
    print(f"Обработано: {len(md_files)}")
    print(f"  Исправлено: {stats['cleaned']}")
    print(f"  Пропущено: {stats['skipped']}")
    print(f"  Ошибок: {stats['errors']}")
    
    if errors:
        print(f"\nОшибки ({len(errors)}):")
        for err in errors[:10]:  # показываем первые 10
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... и ещё {len(errors) - 10}")
    
    if args.dry_run and stats["cleaned"] > 0:
        print(f"\n💡 Запустите без --dry-run для применения изменений")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

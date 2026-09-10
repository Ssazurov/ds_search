"""issue #93: отчёт по документам с needs_review=True (незаполненные
обязательные поля схемы GAR после classify+gar_mapping) — по образцу
rejected_report.py.

Читает data/raw/<source>/*.json (кроме rejected/), пишет
data/raw/<source>/needs_review_report.md.

Запуск: python -m scripts.needs_review_report [source_name]
Без аргумента — обрабатывает все источники в data/raw/.
"""
import json
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
_TRACKED_FIELDS = ("age", "target_audience", "direction", "category", "doc_type")


def _missing_fields(item: dict) -> list[str]:
    return [f for f in _TRACKED_FIELDS if not item.get(f)]


def build_report(source_dir: Path) -> str:
    items = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(source_dir.glob("*.json"))
    ]
    flagged = [it for it in items if it.get("needs_review")]
    if not flagged:
        return ""

    lines = [f"# Отчёт needs_review — {source_dir.name}", ""]
    lines.append(f"Всего требует проверки: {len(flagged)} из {len(items)}\n")
    for it in flagged:
        title = it.get("title") or "(без заголовка)"
        missing = ", ".join(_missing_fields(it)) or "?"
        lines.append(f"- [{title}]({it.get('source_url', '')}) — не заполнено: {missing}")
    return "\n".join(lines)


def main():
    targets = [RAW_DIR / sys.argv[1]] if len(sys.argv) > 1 else [
        d for d in RAW_DIR.iterdir() if d.is_dir()
    ]
    for source_dir in targets:
        report = build_report(source_dir)
        if not report:
            continue
        out_path = source_dir / "needs_review_report.md"
        out_path.write_text(report, encoding="utf-8")
        print(f"написан {out_path}")


if __name__ == "__main__":
    main()

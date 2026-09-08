"""issue #6: отчёт по отклонённому контенту для ручной проверки.

Читает data/raw/<source>/rejected/*.json, группирует по content_status,
пишет data/raw/<source>/rejected_report.md (url, title, причина, метрики).

Запуск: python -m scripts.rejected_report [source_name]
Без аргумента — обрабатывает все источники в data/raw/.
"""
import json
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def build_report(source_dir: Path) -> str:
    rejected_dir = source_dir / "rejected"
    if not rejected_dir.exists():
        return ""
    items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(rejected_dir.glob("*.json"))]
    if not items:
        return ""

    by_status: dict[str, list[dict]] = {}
    for it in items:
        by_status.setdefault(it.get("content_status", "unknown"), []).append(it)

    lines = [f"# Отчёт по отклонённому контенту — {source_dir.name}", ""]
    lines.append(f"Всего отклонено: {len(items)}\n")
    for status, group in sorted(by_status.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {status} ({len(group)})\n")
        for it in group:
            extra = ""
            if "link_to_text_ratio" in it:
                extra = f", LTR={it['link_to_text_ratio']}"
            elif "fit_markdown_chars" in it:
                extra = f", chars={it['fit_markdown_chars']}"
            title = it.get("title") or "(без заголовка)"
            lines.append(f"- [{title}]({it.get('source_url', '')}){extra}")
        lines.append("")
    return "\n".join(lines)


def main():
    targets = [RAW_DIR / sys.argv[1]] if len(sys.argv) > 1 else [
        d for d in RAW_DIR.iterdir() if d.is_dir()
    ]
    for source_dir in targets:
        report = build_report(source_dir)
        if not report:
            continue
        out_path = source_dir / "rejected_report.md"
        out_path.write_text(report, encoding="utf-8")
        print(f"написан {out_path}")


if __name__ == "__main__":
    main()

"""issue #142 (ADR-0007 п.3): детект "битых" файлов — устойчивая эвристика.

Признак поломки: в тексте .md встречается буквальная двухсимвольная
последовательность backslash+n (`\\n` как escape-строка внутри содержимого),
а не настоящий перевод строки. Старая эвристика "1 строка"/"мало строк"
отклонена (ADR-0007) — ложные срабатывания на коротких валидных статьях.

Запуск: python -m scripts.detect_broken_files [source_name]
Без аргумента — обрабатывает все источники в data/raw/.
Пишет data/raw/<source>/broken_files_report.md (doc_id, url, кол-во вхождений).
"""
import json
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

LITERAL_NEWLINE = "\\n"  # буквальные backslash+n, не настоящий \n


def find_broken(source_dir: Path) -> list[dict]:
    broken = []
    for md_path in sorted(source_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        count = text.count(LITERAL_NEWLINE)
        if count == 0:
            continue
        doc_id = md_path.stem
        json_path = source_dir / f"{doc_id}.json"
        url = ""
        if json_path.is_file():
            try:
                url = json.loads(json_path.read_text(encoding="utf-8")).get("source_url", "")
            except (json.JSONDecodeError, OSError):
                pass
        broken.append({"doc_id": doc_id, "source_url": url, "literal_newline_count": count})
    return broken


def build_report(source_dir: Path, broken: list[dict]) -> str:
    lines = [f"# Отчёт по битым файлам (буквальные \\n) — {source_dir.name}", ""]
    lines.append(f"Всего найдено: {len(broken)}\n")
    for it in sorted(broken, key=lambda x: -x["literal_newline_count"]):
        lines.append(f"- {it['doc_id']} ({it['literal_newline_count']} вхождений) — {it['source_url']}")
    return "\n".join(lines)


def main():
    targets = [RAW_DIR / sys.argv[1]] if len(sys.argv) > 1 else [
        d for d in RAW_DIR.iterdir() if d.is_dir()
    ]
    for source_dir in targets:
        if not source_dir.is_dir():
            continue
        broken = find_broken(source_dir)
        if not broken:
            continue
        out_path = source_dir / "broken_files_report.md"
        out_path.write_text(build_report(source_dir, broken), encoding="utf-8")
        print(f"написан {out_path} ({len(broken)} битых)")


if __name__ == "__main__":
    main()

"""Выбрать одну категорию статьи из списка категорий СД через LLM."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metadata.classify import load_llm_config
from src.news.llm_draft import call_llm, parse_llm_json


DEFAULT_CATEGORIES_PATH = (
    Path(__file__).resolve().parents[3]
    / "gar-core-api"
    / "docs"
    / "Направления_Категории_СД.md"
)
_SUBCATEGORY_RE = re.compile(r"^\s*[├└]─\s+(.+?)\s*$")
_DIRECTION_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_TEXT_LIMIT = 4000


def _local_path(path: Path) -> Path:
    """Преобразовать распространённый WSL UNC-путь в Linux-путь."""
    value = str(path)
    # В shell один из ведущих обратных слешей UNC-пути может быть съеден
    # экранированием. Принимаем оба представления, чтобы команда из Windows
    # и тот же аргумент, переданный через Linux shell, работали одинаково.
    for prefix in (
        r"\\wsl.localhost\Ubuntu",
        r"\wsl.localhost\Ubuntu",
        r"\\wsl$\Ubuntu",
        r"\wsl$\Ubuntu",
    ):
        if value.lower().startswith(prefix.lower()):
            return Path(value[len(prefix) :].replace("\\", "/"))
    return path


def parse_categories(markdown: str) -> list[tuple[str, str]]:
    """Извлечь пары «направление, категория» из Markdown-списка."""
    pairs: list[tuple[str, str]] = []
    direction: str | None = None
    for line in markdown.splitlines():
        direction_match = _DIRECTION_RE.match(line)
        if direction_match:
            direction = direction_match.group(1)
            continue
        category_match = _SUBCATEGORY_RE.match(line)
        if direction and category_match:
            pairs.append((direction, category_match.group(1)))
    if not pairs:
        raise ValueError("В файле категорий не найдено ни одной подкатегории")
    return pairs


def build_prompt(title: str, text: str, categories: list[tuple[str, str]]) -> str:
    """Построить строгий промпт с допустимыми категориями."""
    options = "\n".join(
        f"{idx}. {direction} / {category}"
        for idx, (direction, category) in enumerate(categories, start=1)
    )
    return "\n".join(
        [
            "Проанализируй статью о синдроме Дауна и выбери ровно одну наиболее подходящую категорию.",
            "Ответь ТОЛЬКО одним числом — номер категории из списка.",
            "Не добавляй текст, не используй JSON, не объясняй выбор.",
            "",
            "Допустимые варианты:",
            options,
            "",
            f"Заголовок: {title}",
            "Текст статьи:",
            "---",
            text[:_TEXT_LIMIT],
            "---",
            "",
            "Ответ: только номер категории.",
        ]
    )


def classify_article(
    article_path: Path,
    categories_path: Path = DEFAULT_CATEGORIES_PATH,
) -> dict[str, str]:
    """Классифицировать статью и проверить ответ LLM по списку категорий."""
    article_path = _local_path(article_path)
    article = article_path.read_text(encoding="utf-8")
    categories = parse_categories(categories_path.read_text(encoding="utf-8"))
    title = next(
        (line.lstrip("# ").strip() for line in article.splitlines() if line.startswith("#")),
        article_path.stem,
    )
    raw = call_llm(build_prompt(title, article, categories), load_llm_config())
    text = raw.strip()
    if not text.isdigit():
        raise ValueError(f"LLM вернула не число: {text!r}")
    index = int(text) - 1
    if not (0 <= index < len(categories)):
        raise ValueError(
            "LLM вернула категорию вне списка: "
            f"index={int(text)!r}, count={len(categories)}"
        )
    direction, category = categories[index]
    return {
        "direction": direction,
        "category": category,
        "reason": "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path, help="Путь к Markdown-статье")
    parser.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES_PATH,
        help="Путь к файлу Направления_Категории_СД.md",
    )
    args = parser.parse_args(argv)
    print(json.dumps(classify_article(args.article, args.categories), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

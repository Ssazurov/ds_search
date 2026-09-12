import json
from pathlib import Path
from unittest.mock import patch

from scripts import classify_article


CATEGORIES = """\
1. ЗДОРОВЬЕ
   ├─ Психическое здоровье
6. ПОДДЕРЖКА СЕМЬИ
   ├─ Психологическая поддержка на всех этапах
"""


def test_parse_categories_keeps_parent_direction():
    assert classify_article.parse_categories(CATEGORIES) == [
        ("ЗДОРОВЬЕ", "Психическое здоровье"),
        ("ПОДДЕРЖКА СЕМЬИ", "Психологическая поддержка на всех этапах"),
    ]


def test_local_path_converts_wsl_unc_path():
    assert classify_article._local_path(Path(r"\\wsl.localhost\Ubuntu\home\vector\a.md")) == Path(
        "/home/vector/a.md"
    )
    assert classify_article._local_path(Path(r"\wsl.localhost\Ubuntu\home\vector\a.md")) == Path(
        "/home/vector/a.md"
    )


def test_classify_article_accepts_only_exact_pair(tmp_path: Path):
    article = tmp_path / "article.md"
    categories = tmp_path / "categories.md"
    article.write_text("# Заголовок\nТекст", encoding="utf-8")
    categories.write_text(CATEGORIES, encoding="utf-8")

    with patch.object(
        classify_article,
        "call_llm",
        return_value="2",
    ), patch.object(classify_article, "load_llm_config", return_value=object()):
        result = classify_article.classify_article(article, categories)

    assert result["category"] == "Психологическая поддержка на всех этапах"
    assert result["direction"] == "ПОДДЕРЖКА СЕМЬИ"


def test_classify_article_rejects_unknown_category(tmp_path: Path):
    article = tmp_path / "article.md"
    categories = tmp_path / "categories.md"
    article.write_text("Текст", encoding="utf-8")
    categories.write_text(CATEGORIES, encoding="utf-8")

    with patch.object(
        classify_article,
        "call_llm",
        return_value="99",
    ), patch.object(classify_article, "load_llm_config", return_value=object()):
        try:
            classify_article.classify_article(article, categories)
        except ValueError as exc:
            assert "вне списка" in str(exc)
        else:
            raise AssertionError("Ожидалась ошибка для неизвестной категории")

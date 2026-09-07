"""issue #6: link_to_text_ratio должен разделять статьи и каталоги на тех же
данных, что были получены при ручном разборе корпуса (issue #6, комментарий
от 2026-08-27)."""
from src.crawler.filters import link_to_text_ratio, LTR_THRESHOLD


def test_article_below_threshold():
    md = "Синдром Дауна встречается " + "у одного из 700 новорождённых. " * 20
    md += "Подробнее в [источнике](http://x)."
    assert link_to_text_ratio(md) < LTR_THRESHOLD


def test_catalog_above_threshold():
    intro = "Раздел книг для родителей. "
    links = "".join(f"[Книга {i} про воспитание и развитие ребёнка](http://x/{i})\n" for i in range(10))
    md = intro + links
    assert link_to_text_ratio(md) > LTR_THRESHOLD


def test_empty_markdown_is_zero():
    assert link_to_text_ratio("") == 0.0
    assert link_to_text_ratio("   ") == 0.0

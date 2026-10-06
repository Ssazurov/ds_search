"""issue #562: strip_orphaned_underscore_emphasis."""
from src.crawler.md_tables import strip_orphaned_underscore_emphasis as f


def test_lone_underscore_line():
    assert f("a\n\n_  \n\nb") == "a\n\n  \n\nb"


def test_img_prefix_orphan():
    assert f("_![x](u)  ") == "![x](u)  "


def test_valid_pairs_kept():
    for s in ("_![](u)_", "« _подарив_ » x", "_— Даня!_ — Т.", "см. _текст_."):
        assert f(s) == s


def test_url_and_intraword_untouched():
    s = "![a_b](https://x.org/mol_2890.jpg) snake_case_name"
    assert f(s) == s


def test_orphan_open_dropped_across_paragraphs():
    assert f("_«Жизнь\n\nМы") == "«Жизнь\n\nМы"

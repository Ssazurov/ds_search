"""issue #460"""
import importlib.util
from pathlib import Path

_p = Path(__file__).parent.parent / "src" / "crawler" / "md_tables.py"
_s = importlib.util.spec_from_file_location("md_tables", _p)
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)


def test_collapse_multiline_table():
    src = "Text\n\n|\n  \nA  \n \n |\n\nB\n |\n| --- | --- |\n|\n x\n |\n y\n |\n\nAfter"
    out = _m.collapse_multiline_tables(src)
    assert out == "Text\n\n| A | B |\n| --- | --- |\n| x | y |\n\nAfter"


def test_single_line_table_untouched():
    src = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    assert _m.collapse_multiline_tables(src) == src

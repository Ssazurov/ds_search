"""Настройки колонок таблиц (issue #272): слияние, сохранение, битые данные."""
from ui.table_utils import load_prefs, merge_settings, save_prefs

COLS = ["select", "title", "url", "domain", "status"]
PINNED = ("select", "title")


def test_defaults_when_no_saved():
    s = merge_settings(None, COLS, PINNED)
    assert s == {"order": COLS, "hidden": [], "widths": {}}


def test_new_columns_appended_removed_skipped():
    saved = {"order": ["title", "gone", "select", "domain"], "hidden": ["gone", "url"]}
    s = merge_settings(saved, COLS, PINNED)
    assert s["order"] == ["title", "select", "domain", "url", "status"]
    assert s["hidden"] == ["url"]


def test_pinned_never_hidden_and_bad_widths_dropped():
    saved = {"hidden": ["title", "domain"], "widths": {"domain": "large", "url": "huge", "gone": "small"}}
    s = merge_settings(saved, COLS, PINNED)
    assert s["hidden"] == ["domain"]
    assert s["widths"] == {"domain": "large"}


def test_garbage_saved_values():
    assert merge_settings({"order": None, "hidden": 5, "widths": [1]}, COLS, PINNED) == {
        "order": COLS, "hidden": [], "widths": {}}
    s = merge_settings("junk", COLS, PINNED)
    assert s["order"] == COLS


def test_save_load_roundtrip_and_broken_file(tmp_path):
    p = tmp_path / "cfg" / "ui_prefs.json"
    assert load_prefs(p) == {}
    save_prefs({"documents": {"order": ["title"]}}, p)
    assert load_prefs(p) == {"documents": {"order": ["title"]}}
    p.write_text("{broken", encoding="utf-8")
    assert load_prefs(p) == {}

import pytest

from ui import words_tab as wt

CORE = """source: t
categories:
  food:
    age: [1, 4]
    words:
      - {id: bread, ru: хлеб, pos: n, prio: 1}
      - {id: "to_bake", ru: "печь", pos: v, tr: {en: "to bake"}, src: "x"}
"""


@pytest.fixture()
def root(tmp_path):
    (tmp_path / "words").mkdir()
    (tmp_path / "words" / "core.yaml").write_text(CORE, "utf-8")
    return tmp_path


def _text(root):
    return (root / "words" / "core.yaml").read_text("utf-8")


def test_set_tr_add_and_replace(root):
    wt.edit_word(root, "bread", tr={"en": "bread"})
    wt.edit_word(root, "to_bake", tr={"en": "bake", "de": "backen"}, pos="n")
    t = _text(root)
    assert '{id: bread, ru: хлеб, pos: n, prio: 1, tr: {en: "bread"}}' in t
    assert 'pos: n, tr: {en: "bake", de: "backen"}' in t


def test_edit_ru_and_delete(root):
    wt.edit_word(root, "to_bake", tr={"ru": "выпекать"})
    assert 'ru: "выпекать"' in _text(root)
    assert wt.edit_word(root, "bread", delete=True)
    assert "id: bread" not in _text(root)
    assert not wt.edit_word(root, "nope")


def test_add_word_and_dup(root):
    wt.add_word(root, "toys", "ball", "мяч", "n", 1, {"en": "ball"}, {"bread"})
    d = (root / "words" / wt.MANUAL).read_text("utf-8")
    assert "id: ball" in d and "ru: мяч" in d
    wt.add_word(root, "toys", "doll", "кукла", "n", 2, None, {"bread", "ball"})
    assert wt.edit_word(root, "doll", tr={"en": "doll"})
    with pytest.raises(ValueError):
        wt.add_word(root, "toys", "ball", "мяч", "n", 2, None, {"ball"})
    with pytest.raises(ValueError):
        wt.add_word(root, "toys", "Bad id", "x", "n", 2)


def test_stage_toggle_and_counts():
    dec = {}
    wt.toggle_verdict(dec, "bread", "ok")
    assert dec == {"bread": {"verdict": "ok"}}
    wt.toggle_verdict(dec, "bread", "ok")
    assert dec == {}
    wt.stage(dec, "bread", "en", "bread", "")
    wt.stage(dec, "bread", "de", "Brot", "")
    wt.stage(dec, "bread", "ru", "хлеб", "хлеб")  # равно исходному — правки нет
    wt.toggle_verdict(dec, "bread", "del")
    assert dec == {"bread": {"en": "bread", "tr": {"de": "Brot"}, "verdict": "del"}}
    assert wt.counts(dec) == {"ok": 0, "del": 1, "edit": 1}
    wt.stage(dec, "bread", "en", "")
    wt.stage(dec, "bread", "de", "")
    assert dec == {"bread": {"verdict": "del"}}


def test_clean_merge_and_legacy_format(root):
    assert wt.clean_entry("del") == {"verdict": "del"}
    assert wt.clean_entry({"verdict": "x", "pos": "zz", "ru": " "}) == {}
    dec = {"a": {"tr": {"de": "x"}}}
    assert wt.merge_decisions(dec, {"a": {"verdict": "ok", "tr": {"fr": "y"}}, "Bad id": {"verdict": "ok"}}) == 1
    assert dec == {"a": {"tr": {"de": "x", "fr": "y"}, "verdict": "ok"}}
    (root / "review").mkdir()
    (root / "review" / "ui_decisions.json").write_text('{"bread": "ok"}', "utf-8")
    assert wt.load_decisions(root) == {"bread": {"verdict": "ok"}}


def test_apply_decisions(root):
    wt.save_decisions(root, {"bread": {"verdict": "del"},
                             "to_bake": {"verdict": "ok", "ru": "жарить", "pos": "n", "tr": {"de": "backen"}}})
    assert wt.apply_decisions(root) == {"del": 1, "edit": 1}
    t = _text(root)
    assert "id: bread" not in t
    assert 'ru: "жарить", pos: n' in t and 'de: "backen"' in t
    assert wt.load_decisions(root) == {"to_bake": {"verdict": "ok"}}


ROWS = [
    {"id": "a", "cat": "food", "tr": {"ru": "а", "en": "a"}, "flags": [], "img": True, "audio": ["ru"], "review": "ok"},
    {"id": "b", "cat": "toys", "tr": {"ru": "б"}, "flags": ["дубль en: a"], "img": False, "audio": [], "review": ""},
]


def test_filter_rows():
    ls = ["ru", "en"]
    ids = lambda m, c="все", q="": [r["id"] for r in wt.filter_rows(ROWS, m, c, q, ls)]
    assert ids("flagged") == ["b"] and ids("dups") == ["b"]
    assert ids("no_tr") == ["b"] and ids("no_img") == ["b"]
    assert ids("unreviewed") == ["b"] and ids("no_audio") == ["a", "b"]
    assert ids("all", "food") == ["a"] and ids("all", q="Б") == ["b"]
    assert wt.langs_of(ROWS, ["de"]) == ["ru", "de", "en"]


def test_labels_ru():
    assert wt.cat_label("food") == "Еда" and wt.cat_label("zzz") == "zzz"
    assert wt.lang_label("ru") == "Русский" and wt.lang_label("xx") == "xx"
    assert set(wt.POS_RU) == set(wt.POS)

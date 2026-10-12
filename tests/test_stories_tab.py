"""Смоук вкладки «Истории» (ds_search#614): рендерится без исключений на каталоге ds_words (DS_WORDS_DIR)."""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

W = os.environ.get("DS_WORDS_DIR", "")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(W, "scripts/storygen.py")),
                                reason="нет DS_WORDS_DIR со storygen.py")


def _app():
    from ui import stories_tab
    stories_tab.render()


def test_render():
    at = AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception
    assert any("Создать" in e.label for e in at.expander)


def test_strip(tmp_path):
    from PIL import Image
    from ui import stories_tab

    class SG:
        @staticmethod
        def work(sid):
            return tmp_path

    for n in ("a", "b"):
        Image.new("RGB", (64, 64), "red").save(tmp_path / f"{n}.png")
    story = {"steps": [{"id": "s1", "text": {"ru": "Я мою руки"}}, {"id": "s2", "text": {"ru": "Пусто"}}]}
    state = {"steps": {
        "s1": {"selected": "a", "variants": [{"id": "a", "file": "a.png"}, {"id": "b", "file": "b.png", "liked": True}]},
        "s2": {"selected": None, "variants": []}}}
    png = stories_tab._strip(SG, "x", story, state)
    im = Image.open(__import__("io").BytesIO(png))
    assert im.size == (640, 90 + 2 * 320)


def test_new_step_ids():
    from ui import stories_tab
    st_ = {"steps": [{"id": "s1", "text": {"ru": "а"}, "location": "bathroom", "outfit": "home"}, {"id": "s7", "text": {"ru": "б"}, "location": "hallway", "outfit": "pajamas"}]}
    stories_tab._new_step(st_, "в")
    n = st_["steps"][-1]
    assert n["id"] == "s8" and n["text"]["ru"] == "в" and n["location"] == "hallway" and n["outfit"] == "pajamas"


def test_ru_keeps_en():
    from ui import stories_tab
    old = {"ru": "а", "en": "a"}
    assert stories_tab._ru(old, "а") is old
    assert stories_tab._ru(old, "б") == {"ru": "б"}
    assert stories_tab._ru(None, "в") == {"ru": "в"}


def test_scenes_store(tmp_path, monkeypatch):
    from ui import stories_tab
    sg = stories_tab._sg()
    if not hasattr(sg, "sgen"):
        pytest.skip("storygen без сцен")
    monkeypatch.setattr(sg, "ROOT", tmp_path)
    monkeypatch.setattr(sg, "_upload", lambda png, name: name)
    monkeypatch.setattr(sg, "_gen", lambda prompt, seed, refs: b"png")
    sg.lib_save("items", {"towel": {"title": {"ru": "П"}, "desc": {"en": "yellow towel"}}})
    sg.lib_save("scenes", {"bath": {"title": {"ru": "В"}, "desc": {"en": "small bathroom"}, "camera": {"en": "front view"},
                                    "items": [{"item": "towel", "place": {"en": "on the hook"}}]}})
    p = sg.scene_prompt("bath")
    assert p.startswith("Empty room") and "yellow towel on the hook" in p and "front view" in p
    v = sg.sgen("bath", 3)
    assert len(v) == 3 and len(sg.sload("bath")["variants"]) == 3
    sg.sselect("bath", v[0]["id"]); sg.slike("bath", v[1]["id"])
    assert sg.sprune("bath") == 1
    sg.sdelete("bath", v[0]["id"])
    st_ = sg.sload("bath")
    assert st_["selected"] is None and [x["id"] for x in st_["variants"]] == [v[1]["id"]]


def test_items_store(tmp_path, monkeypatch):
    from ui import stories_tab
    sg = stories_tab._sg()
    if not hasattr(sg, "holders"):
        pytest.skip("storygen без держателей предметов")
    monkeypatch.setattr(sg, "ROOT", tmp_path)
    monkeypatch.setattr(sg, "_upload", lambda png, name: name)
    monkeypatch.setattr(sg, "_gen", lambda prompt, seed, refs: b"png")
    monkeypatch.setattr(sg, "_square", lambda p: b"x")
    monkeypatch.setattr(sg, "hero_ref", lambda ch, h, o: tmp_path / "h.png")
    ch = {"characters": {
        "hero": {"kind": "hero", "variants": {"girl": {}, "boy": {}}, "outfits": {"home": {"desc": "pink t-shirt"}}},
        "mom": {"name": {"ru": "Мама"}, "bible": "a kind woman", "refs": ["refs/mom.png"]}}}
    monkeypatch.setattr(sg, "registry", lambda: ch)
    assert list(sg.holders()) == ["girl", "boy", "mom"] and sg.holders()["mom"] == "Мама"
    sg.lib_save("items", {"towel": {"title": {"ru": "П"}, "desc": {"en": "yellow towel"}}})
    assert "neutral background" in sg.item_prompt("towel", "view")
    assert "holding yellow towel" in sg.item_prompt("towel", "hand:girl")
    v = sg.igen("towel", "view", 2)
    sg.iselect("towel", "view", v[0]["id"])
    assert "Image 2 is yellow towel" in sg.item_prompt("towel", "hand:boy")
    assert "Image 1 is a kind woman" in sg.item_prompt("towel", "hand:mom")
    h = sg.igen("towel", "hand:boy", 2)
    sg.ilike("towel", "hand:boy", h[0]["id"])
    sg.igen("towel", "hand:mom", 1)
    assert sg.iprune("towel") == 3          # view[1], hand:boy[1], hand:mom[0]
    sg.idelete("towel", "view", v[0]["id"])
    st_ = sg.iload("towel")
    assert st_["view"]["selected"] is None and not st_["view"]["variants"] and len(st_["hand:boy"]["variants"]) == 1


def test_chars_tab():
    at = AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception
    assert any(s.label == "Персонаж" for s in at.selectbox)

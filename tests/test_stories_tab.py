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

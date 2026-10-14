"""Смоук страницы «Картинки» (ds_search#695) и g*-функций storygen."""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

W = os.environ.get("DS_WORDS_DIR", "")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(W, "scripts/storygen.py")),
                                reason="нет DS_WORDS_DIR со storygen.py")


def _app():
    from ui import images_tab
    images_tab.render()


def test_render():
    at = AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception
    assert any(b.label == "Сгенерировать" for b in at.button) or at.get("form_submit_button")


def test_history(tmp_path):
    from ui.stories_tab import _sg
    sg = _sg()
    old = sg.ROOT
    sg.ROOT = tmp_path
    try:
        rid = sg.gnew("тест")
        assert any(r["id"] == rid for r in sg.gload()["runs"])
        sg.gdelete_run(rid)
        assert not sg.gload()["runs"]
    finally:
        sg.ROOT = old

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

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


def test_size():
    from ui.stories_tab import _sg
    sg = _sg()
    assert all(w % 16 == 0 and h % 16 == 0 and w * h <= sg.SIZE_MAXPX for w, h in sg.PRESETS.values())
    assert sg.norm_size() == (768, 768)
    assert sg.norm_size(100, 5000) == (256, 2048) or sg.norm_size(100, 5000)[0] * sg.norm_size(100, 5000)[1] <= sg.SIZE_MAXPX
    w, h = sg.norm_size(2048, 2048)
    assert w * h <= sg.SIZE_MAXPX * 1.02 and w % 16 == 0 and h % 16 == 0
    assert sg.norm_size(1000, 500) == (992, 496)


def test_fit(tmp_path):
    from PIL import Image
    from ui.stories_tab import _sg
    import io
    sg = _sg()
    p = tmp_path / "a.png"; Image.new("RGB", (400, 400), "red").save(p)
    im = Image.open(io.BytesIO(sg._fit(p, 1024, 576)))
    assert im.size == (1024, 576)
    assert im.getpixel((512, 288)) == (255, 0, 0) and im.getpixel((5, 5)) == (255, 255, 255)


def test_size_row():
    at = AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception
    at.selectbox(key="img_fmt").select("16:9").run()
    assert (at.number_input(key="img_w").value, at.number_input(key="img_h").value) == (1024, 576)
    at.number_input(key="img_w").set_value(800).run()
    assert at.selectbox(key="img_fmt").value == "Свой"

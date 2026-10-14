"""usage/delete_* storygen с учётом привязок (ds_search#702)."""
import os

import pytest

pytest.importorskip("streamlit")
yaml = pytest.importorskip("yaml")
W = os.environ.get("DS_WORDS_DIR", "")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(W, "scripts/storygen.py")), reason="нет DS_WORDS_DIR")


def test_delete(tmp_path):
    from ui.stories_tab import _sg
    sg = _sg(); old = sg.ROOT; sg.ROOT = tmp_path
    try:
        (tmp_path / "library").mkdir(); (tmp_path / "stories").mkdir()
        sg.lib_save("scenes", {"sc1": {"title": {"ru": "С"}, "items": [{"item": "it1"}]}, "sc2": {"title": {"ru": "С2"}, "items": []}})
        sg.lib_save("items", {"it1": {"title": {"ru": "П"}, "desc": {"ru": ""}}})
        story = {"id": "s1", "title": {"ru": "И"}, "steps": [{"id": "a", "text": {"ru": "x"}, "scene": "sc1", "uses": ["it1"]}]}
        (tmp_path / "stories/s1.yaml").write_text(yaml.safe_dump(story), encoding="utf-8")
        assert sg.usage("scene", "sc1")[0] == ["s1/a"] and sg.usage("item", "it1")[0] == ["s1/a"]
        with pytest.raises(ValueError):
            sg.delete_item("it1")
        sg.delete_scene("sc2")
        assert "sc2" not in sg.lib("scenes")
        story["steps"] = [{"id": "a", "text": {"ru": "x"}}]
        (tmp_path / "stories/s1.yaml").write_text(yaml.safe_dump(story), encoding="utf-8")
        assert sg.usage("item", "it1")[1] == ["сцена sc1"]
        sg.delete_item("it1")
        assert sg.lib("scenes")["sc1"]["items"] == [] and "it1" not in sg.lib("items")
    finally:
        sg.ROOT = old

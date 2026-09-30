from pathlib import Path

from src.crawler.manual_add import _resolve_source


def test_registry_source_uses_domain_folder(tmp_path):
    cfg, out = _resolve_source("downsideup.org", tmp_path)
    assert out == tmp_path / "downsideup.org"


def test_unknown_domain_folder(tmp_path):
    _, out = _resolve_source("example.ru", tmp_path)
    assert out == tmp_path / "example.ru"

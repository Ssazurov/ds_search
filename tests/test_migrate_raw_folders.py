"""Tests for migrate_raw_folders script (issue #400)."""
import json
import tempfile
from pathlib import Path

import pytest

from scripts.migrate_raw_folders import resolve_target_folder, scan_wrong_folders


def test_resolve_target_folder_for_sources_domain(tmp_path):
    """Домен из SOURCES использует его папку."""
    target = resolve_target_folder("downsideup.org", tmp_path)
    assert target == tmp_path / "downsideup.org"


def test_resolve_target_folder_for_unknown_domain(tmp_path):
    """Неизвестный домен использует domain_dirname."""
    target = resolve_target_folder("example.com", tmp_path)
    assert target == tmp_path / "example.com"


def test_resolve_target_folder_for_cyrillic_domain(tmp_path):
    """Кириллический домен транслитерируется."""
    target = resolve_target_folder("город-надежды.рф", tmp_path)
    assert target == tmp_path / "gorod-nadezhdy-rf"


def test_resolve_target_folder_for_www_prefix(tmp_path):
    """www. префикс удаляется."""
    target = resolve_target_folder("www.example.com", tmp_path)
    assert target == tmp_path / "example.com"


def test_scan_wrong_folders_skips_ds_search_internal(tmp_path):
    """Файлы с source_domain=ds_search пропускаются."""
    wrong_folder = tmp_path / "glossary_items"
    wrong_folder.mkdir()
    
    json_file = wrong_folder / "test.json"
    json_file.write_text(json.dumps({
        "source_domain": "ds_search",
        "title": "Test"
    }))
    
    migrations = scan_wrong_folders(tmp_path)
    assert len(migrations) == 0


def test_scan_wrong_folders_finds_links_items(tmp_path):
    """Файлы из links_items попадают в миграцию."""
    wrong_folder = tmp_path / "links_items"
    wrong_folder.mkdir()
    
    json_file = wrong_folder / "link-001.json"
    json_file.write_text(json.dumps({
        "source_domain": "example.com",
        "title": "Example"
    }))
    
    migrations = scan_wrong_folders(tmp_path)
    assert len(migrations) == 1
    assert migrations[0][0] == json_file
    assert migrations[0][2] == tmp_path / "example.com"


def test_scan_wrong_folders_skips_correct_folders(tmp_path):
    """Файлы уже в правильных папках не попадают в миграцию."""
    correct_folder = tmp_path / "example.com"
    correct_folder.mkdir()
    
    json_file = correct_folder / "doc.json"
    json_file.write_text(json.dumps({
        "source_domain": "example.com",
        "title": "Example"
    }))
    
    migrations = scan_wrong_folders(tmp_path)
    assert len(migrations) == 0

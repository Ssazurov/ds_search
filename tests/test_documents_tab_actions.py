"""Охранный тест ряда действий вкладки «Документы» (issue #432).

Фиксирует порядок кнопок и их подписи: замена переключателя «Формат» двумя
кнопками «В пересказ» / «В новости» и короткие подписи без слова «выбранные».
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).parent.parent / "ui" / "documents_tab.py").read_text(encoding="utf-8")

_BUTTON_RE = re.compile(r'\bb\d\.button\(\s*f?"([^"]+)"')


def _row() -> dict[str, str]:
    """Номер колонки (b1..bN) -> подпись кнопки, в порядке вызовов."""
    return {m.group(0).split(".")[0]: m.group(1) for m in _BUTTON_RE.finditer(SRC)}


def test_action_row_has_seven_columns():
    assert 'action_row(7, "documents")' in SRC


def test_button_order():
    assert _row() == {
        "b1": "Загрузить в GAR ({len(not_loaded)})",
        "b2": "Удалить из GAR ({len(gar_only)})",
        "b3": "Удалить везде ({len(selected_rows)})",
        "b4": "Архивировать ({len(archivable)})",
        "b5": "Из архива ({len(archivable)})",
        "b6": "В пересказ ({len(with_url)})",
        "b7": "В новости ({len(with_url)})",
    }


def test_labels_drop_selected_word():
    for label in ("Загрузить в GAR", "Архивировать"):
        assert f'"{label} выбранные' not in SRC


def test_no_format_radio_on_documents_tab():
    """Переключатель формата заменён кнопками — радио «Формат» тут не нужен (#432)."""
    assert "format_selector" not in SRC


def test_digest_and_news_use_distinct_keys_and_formats():
    assert 'key="doc_to_digest_btn"' in SRC
    assert 'key="doc_to_news_btn"' in SRC
    assert '_to_news_batch(with_url, fmt="digest")' in SRC
    assert '_to_news_batch(with_url, fmt="news")' in SRC


def test_digest_button_has_help_about_cheklist():
    """Смысл help, который раньше жил на format_selector, перенесён на кнопку."""
    help_block = SRC.split('key="doc_to_digest_btn"', 1)[1].split("):", 1)[0]
    assert "чеклист" in help_block
    assert "ссылкой на источник" in help_block

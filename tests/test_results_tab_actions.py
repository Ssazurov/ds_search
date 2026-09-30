"""Охранный тест ряда действий вкладки «Результаты» (issue #430).

Фиксирует порядок кнопок и их подписи: перестановка «Удалить» за «Отклонить»,
появление отдельной кнопки «В пересказ» вместо радио «Формат» и короткие
подписи статусных действий без слова «выбранные».
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).parent.parent / "ui" / "results_tab.py").read_text(encoding="utf-8")

_BUTTON_RE = re.compile(r'\bb\d\.button\(\s*f?"([^"]+)"')


def _row() -> dict[str, str]:
    """Номер колонки (b1..bN) -> подпись кнопки, в порядке вызовов."""
    return {m.group(0).split(".")[0]: m.group(1) for m in _BUTTON_RE.finditer(SRC)}


def test_action_row_has_six_columns():
    assert "action_row(6, \"results\")" in SRC


def test_button_order():
    assert _row() == {
        "b5": "В пересказ",
        "b6": "В новости",
        "b1": "Одобрить",
        "b2": "Отклонить",
        "b4": "В очередь загрузки",
        "b3": "Удалить",
    }


def test_status_labels_drop_selected_word():
    for label in ("Одобрить", "Отклонить", "Удалить"):
        assert f'"{label} выбранные"' not in SRC


def test_no_format_radio_on_results_tab():
    """Переключатель формата заменён кнопками — радио «Формат» тут не нужен (#430)."""
    assert "format_selector" not in SRC


def test_digest_and_news_use_distinct_keys_and_formats():
    assert 'key="results_to_digest"' in SRC
    assert 'key="results_to_news"' in SRC
    assert 'fmt="digest"' in SRC
    assert 'fmt="news"' in SRC


def test_digest_button_has_help_about_cheklist():
    """Смысл help, который раньше жил на format_selector, перенесён на кнопку."""
    help_block = SRC.split('button("В пересказ"', 1)[1].split(")", 1)[0]
    assert "чеклист" in help_block
    assert "ссылкой на источник" in help_block

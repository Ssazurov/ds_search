"""Охранный тест ряда действий вкладки «Результаты» (issue #430, #434).

Фиксирует порядок кнопок и их подписи: перестановка «Удалить» за «Отклонить»,
появление отдельной кнопки «В пересказ» вместо радио «Формат», короткие
подписи статусных действий без слова «выбранные» и кнопку «Скачать» перед
«В пересказ» (то же ядро, что «Скачать» на вкладке «Загрузки»).
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).parent.parent / "ui" / "results_tab.py").read_text(encoding="utf-8")

_BUTTON_RE = re.compile(r'\bb\d\.button\(\s*f?"([^"]+)"')


def _row() -> dict[str, str]:
    """Номер колонки (b1..bN) -> подпись кнопки, в порядке вызовов."""
    return {m.group(0).split(".")[0]: m.group(1) for m in _BUTTON_RE.finditer(SRC)}


def test_action_row_has_seven_columns():
    assert "action_row(7, \"results\")" in SRC


def test_button_order():
    assert _row() == {
        "b5": "Скачать",
        "b6": "В пересказ",
        "b7": "В новости",
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


def test_download_button_uses_shared_core():
    """«Скачать» зовёт то же ядро, что «Скачать» на вкладке «Загрузки» (#434)."""
    assert 'button("Скачать"' in SRC
    assert 'key="results_download"' in SRC
    assert "add_manual_document(" in SRC
    download_block = SRC.split('button("Скачать"', 1)[1].split(")", 1)[0]
    assert "«Загрузки»" in download_block
    assert "_download(rows, selected_ids, settings)" in SRC


def test_download_helper_keeps_batch_and_uses_status_chain():
    """Батч не прерывается на ошибке, статусы downloading → downloaded/error."""
    body = SRC.split("def _download(", 1)[1].split("\ndef render(", 1)[0]
    assert 'status="downloading"' in body
    assert 'status="downloaded"' in body
    assert 'status="error"' in body
    assert 'status="queued"' not in body  # промежуточный queued не выставляем
    assert "except Exception as exc" in body  # сбой на одном элементе не рвёт батч

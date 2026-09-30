"""Тесты кнопки «Скачать» на вкладке «Результаты» (issue #434).

Проверяем контракт `_download` (ui/results_tab.py): статусы
downloading → downloaded/error, отсутствие промежуточного queued, маппинг
особых случаев add_manual_document (added/duplicate/license_denied/failed) и
непрерывание батча при сбое на одном элементе.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace

import pytest

from ui import results_tab

_ROWS = [
    {"id": "1", "url": "https://ex.org/a", "title": "A",
     "suggested_direction": "dir-1", "suggested_category": "cat-1"},
    {"id": "2", "url": "https://ex.org/b", "title": "B"},
    {"id": "3", "url": "https://ex.org/c", "title": "C"},
]


def _run(monkeypatch, results, *, selected_ids=("1", "2", "3"), status_fail=()):
    """Вызывает _download с фейками GAR/краулера/UI, возвращает журнал вызовов."""
    calls: dict = {"status": [], "downloads": [], "reports": [], "reruns": 0}

    class _FakeClient:
        def __init__(self, settings=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update_discovered_source(self, row_id, status=None, **kw):
            if row_id in status_fail:
                raise RuntimeError("GAR недоступен")
            calls["status"].append((row_id, status))

    async def _fake_add_manual_document(url, **kw):
        calls["downloads"].append((url, kw.get("direction"), kw.get("category")))
        outcome = results[url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(results_tab, "GarDiscoveryClient", _FakeClient)
    monkeypatch.setattr(results_tab, "add_manual_document", _fake_add_manual_document)
    monkeypatch.setattr(results_tab.st, "spinner", lambda msg: contextlib.nullcontext())
    monkeypatch.setattr(
        results_tab.st, "rerun", lambda: calls.__setitem__("reruns", calls["reruns"] + 1),
    )
    monkeypatch.setattr(
        results_tab.notify, "report",
        lambda level, title, stats=None, details=None: calls["reports"].append(
            (level, title, stats, details or []),
        ),
    )

    results_tab._download(_ROWS, list(selected_ids), SimpleNamespace())
    return calls


def test_added_marks_downloaded(monkeypatch):
    calls = _run(monkeypatch, {"https://ex.org/a": {"status": "added"}},
                 selected_ids=("1",))
    assert calls["status"] == [("1", "downloading"), ("1", "downloaded")]
    level, title, stats, details = calls["reports"][0]
    assert (level, title) == ("success", "Скачано: 1 из 1")
    assert stats == {"скачано": 1, "дублей": 0, "ошибок": 0}
    assert details == []
    assert calls["reruns"] == 1


def test_no_queued_status_in_chain(monkeypatch):
    """Решение issue #434: queued не выставляется, цепочка downloading → результат."""
    calls = _run(monkeypatch, {"https://ex.org/a": {"status": "added"}},
                 selected_ids=("1",))
    assert all(status != "queued" for _, status in calls["status"])


def test_duplicate_marks_downloaded_and_reports_doc_id(monkeypatch):
    calls = _run(
        monkeypatch,
        {"https://ex.org/a": {"status": "duplicate", "doc_id": "abc123"}},
        selected_ids=("1",),
    )
    assert calls["status"] == [("1", "downloading"), ("1", "downloaded")]
    level, _title, stats, details = calls["reports"][0]
    assert level == "success"  # дубль не ошибка — документ в корпусе
    assert stats == {"скачано": 0, "дублей": 1, "ошибок": 0}
    assert "abc123" in details[0]
    assert "Уже в базе" in details[0]


@pytest.mark.parametrize("status_value", ["license_denied", "license_pending", "failed"])
def test_license_and_failure_marks_error(monkeypatch, status_value):
    calls = _run(
        monkeypatch,
        {"https://ex.org/a": {"status": status_value, "reason": "лицензия/сбой"}},
        selected_ids=("1",),
    )
    assert calls["status"] == [("1", "downloading"), ("1", "error")]
    level, _title, stats, details = calls["reports"][0]
    assert level == "error"
    assert stats == {"скачано": 0, "дублей": 0, "ошибок": 1}
    assert "лицензия/сбой" in details[0]


def test_batch_continues_after_exception(monkeypatch):
    calls = _run(monkeypatch, {
        "https://ex.org/a": {"status": "added"},
        "https://ex.org/b": RuntimeError("таймаут"),
        "https://ex.org/c": {"status": "added"},
    })
    # все три обработаны: сбой второго не остановил батч
    assert [row_id for row_id, _ in calls["status"]] == [
        "1", "1", "2", "2", "3", "3",
    ]
    level, title, stats, details = calls["reports"][0]
    assert (level, title) == ("warning", "Скачано: 2 из 3")
    assert stats == {"скачано": 2, "дублей": 0, "ошибок": 1}
    assert "таймаут" in details[0]


def test_direction_and_category_taken_from_suggestions(monkeypatch):
    calls = _run(monkeypatch, {"https://ex.org/a": {"status": "added"}},
                 selected_ids=("1",))
    assert calls["downloads"] == [("https://ex.org/a", "dir-1", "cat-1")]


def test_missing_suggestions_pass_none(monkeypatch):
    calls = _run(monkeypatch, {"https://ex.org/b": {"status": "added"}},
                 selected_ids=("2",))
    assert calls["downloads"] == [("https://ex.org/b", None, None)]


def test_status_update_failure_does_not_break_batch(monkeypatch):
    """Сбой смены статуса не роняет батч: скачивание уже состоялось."""
    calls = _run(monkeypatch, {
        "https://ex.org/a": {"status": "added"},
        "https://ex.org/b": {"status": "added"},
    }, status_fail=("2",), selected_ids=("1", "2"))
    # не удалось даже поставить downloading — элемент пропущен, батч продолжен
    assert calls["downloads"] == [("https://ex.org/a", "dir-1", "cat-1")]
    level, _title, stats, details = calls["reports"][0]
    assert level == "warning"
    assert stats == {"скачано": 1, "дублей": 0, "ошибок": 1}
    assert "GAR недоступен" in details[0]

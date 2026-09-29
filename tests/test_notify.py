"""Тесты для ui/notify.py (issue #366, подзадача #367)."""
from __future__ import annotations

import pytest

from ui.notify import outcome_level, format_stats, _push_message, _dismiss_message, _push_toast, _pop_toasts


class TestOutcomeLevel:
    """Тесты для outcome_level."""

    def test_total_zero_returns_info(self):
        assert outcome_level(0, 0) == "info"

    def test_all_ok_returns_success(self):
        assert outcome_level(5, 5) == "success"

    def test_partial_ok_returns_warning(self):
        assert outcome_level(3, 5) == "warning"

    def test_none_ok_returns_error(self):
        assert outcome_level(0, 5) == "error"


class TestFormatStats:
    """Тесты для format_stats."""

    def test_empty_dict_returns_empty_string(self):
        assert format_stats({}) == ""

    def test_single_item(self):
        result = format_stats({"найдено": 3})
        assert result == "найдено 3"

    def test_multiple_items(self):
        result = format_stats({"найдено": 3, "новых": 0})
        assert result == "найдено 3 · новых 0"

    def test_preserves_order(self):
        # Python 3.7+ сохраняет порядок вставки в dict
        result = format_stats({"a": 1, "b": 2, "c": 3})
        assert result == "a 1 · b 2 · c 3"


class TestPushDismissMessage:
    """Тесты для _push_message и _dismiss_message."""

    def test_push_message_creates_list(self, monkeypatch):
        session_state = {}
        monkeypatch.setattr("streamlit.session_state", session_state)

        _push_message("Поиск", "success", "Готово", {"найдено": 5}, ["detail1"])

        assert "_notify" in session_state
        messages = session_state["_notify"]
        assert len(messages) == 1
        assert messages[0]["tab"] == "Поиск"
        assert messages[0]["level"] == "success"
        assert messages[0]["title"] == "Готово"
        assert messages[0]["stats"] == {"найдено": 5}
        assert messages[0]["details"] == ["detail1"]
        assert "id" in messages[0]

    def test_push_message_limits_to_5(self, monkeypatch):
        session_state = {}
        monkeypatch.setattr("streamlit.session_state", session_state)

        for i in range(7):
            _push_message("Поиск", "info", f"Msg {i}", None, None)

        messages = session_state["_notify"]
        assert len(messages) == 5
        # Старые вытесняются, остаются последние 5
        assert messages[0]["title"] == "Msg 2"
        assert messages[4]["title"] == "Msg 6"

    def test_dismiss_message_removes_by_id(self, monkeypatch):
        session_state = {"_notify": [
            {"id": "id1", "tab": "Поиск", "level": "info", "title": "A", "stats": {}, "details": []},
            {"id": "id2", "tab": "Поиск", "level": "info", "title": "B", "stats": {}, "details": []},
            {"id": "id3", "tab": "Поиск", "level": "info", "title": "C", "stats": {}, "details": []},
        ]}
        monkeypatch.setattr("streamlit.session_state", session_state)

        _dismiss_message("id2")

        messages = session_state["_notify"]
        assert len(messages) == 2
        assert messages[0]["id"] == "id1"
        assert messages[1]["id"] == "id3"

    def test_dismiss_message_no_state(self, monkeypatch):
        session_state = {}
        monkeypatch.setattr("streamlit.session_state", session_state)

        # Не должно упасть
        _dismiss_message("nonexistent")
        assert "_notify" not in session_state


class TestToasts:
    """Тесты для _push_toast и _pop_toasts."""

    def test_push_toast_creates_queue(self, monkeypatch):
        session_state = {}
        monkeypatch.setattr("streamlit.session_state", session_state)

        _push_toast("Сохранено", "✅")

        assert "_notify_toasts" in session_state
        toasts = session_state["_notify_toasts"]
        assert len(toasts) == 1
        assert toasts[0]["message"] == "Сохранено"
        assert toasts[0]["icon"] == "✅"
        assert "id" in toasts[0]

    def test_push_multiple_toasts(self, monkeypatch):
        session_state = {}
        monkeypatch.setattr("streamlit.session_state", session_state)

        _push_toast("Msg1", "✅")
        _push_toast("Msg2", "📋")

        toasts = session_state["_notify_toasts"]
        assert len(toasts) == 2

    def test_pop_toasts_returns_and_clears(self, monkeypatch):
        session_state = {"_notify_toasts": [
            {"id": "t1", "message": "Msg1", "icon": "✅"},
            {"id": "t2", "message": "Msg2", "icon": "📋"},
        ]}
        monkeypatch.setattr("streamlit.session_state", session_state)

        toasts = _pop_toasts()

        assert len(toasts) == 2
        assert toasts[0]["message"] == "Msg1"
        assert toasts[1]["message"] == "Msg2"

        # Очередь должна быть очищена
        assert session_state["_notify_toasts"] == []

    def test_pop_toasts_empty_state(self, monkeypatch):
        session_state = {}
        monkeypatch.setattr("streamlit.session_state", session_state)

        toasts = _pop_toasts()

        assert toasts == []

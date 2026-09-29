"""Единый вывод сообщений о результатах операций (issue #366).

Сообщения показываются сверху вкладки, переживают st.rerun() и держатся
до закрытия кнопкой ✕. Цвет по исходу: зелёный (всё ок), жёлтый (частично),
красный (ошибка), синий (информация).
"""
from __future__ import annotations

import uuid
from typing import Literal

import streamlit as st

Level = Literal["success", "warning", "error", "info"]


def outcome_level(ok: int, total: int) -> Level:
    """Определяет уровень сообщения по соотношению успешных к общему числу.

    Args:
        ok: Число успешных операций
        total: Общее число операций

    Returns:
        - "info" если total == 0
        - "success" если ok == total
        - "error" если ok == 0
        - "warning" в остальных случаях (частичный успех)
    """
    if total == 0:
        return "info"
    if ok == total:
        return "success"
    if ok == 0:
        return "error"
    return "warning"


def format_stats(stats: dict[str, object]) -> str:
    """Форматирует словарь статистики в строку вида 'ключ значение · ключ значение'.

    Args:
        stats: Словарь со статистикой

    Returns:
        Форматированная строка или пустая строка если stats пустой
    """
    if not stats:
        return ""
    return " · ".join(f"{k} {v}" for k, v in stats.items())


def _push_message(
    tab: str,
    level: Level,
    title: str,
    stats: dict[str, object] | None,
    details: list[str] | None,
) -> None:
    """Добавляет сообщение в очередь с ограничением в 5 штук (внутренняя функция).

    Args:
        tab: Имя вкладки
        level: Уровень сообщения
        title: Заголовок
        stats: Статистика (опционально)
        details: Подробности (опционально)
    """
    if "_notify" not in st.session_state:
        st.session_state["_notify"] = []

    messages = st.session_state["_notify"]
    messages.append({
        "id": str(uuid.uuid4()),
        "tab": tab,
        "level": level,
        "title": title,
        "stats": stats or {},
        "details": details or [],
    })

    # Лимит 5 сообщений, старые вытесняются
    if len(messages) > 5:
        st.session_state["_notify"] = messages[-5:]


def _dismiss_message(msg_id: str) -> None:
    """Удаляет сообщение по ID (внутренняя функция).

    Args:
        msg_id: ID сообщения для удаления
    """
    if "_notify" not in st.session_state:
        return

    messages = st.session_state["_notify"]
    st.session_state["_notify"] = [m for m in messages if m["id"] != msg_id]


def report(
    level: Level,
    title: str,
    stats: dict[str, object] | None = None,
    details: list[str] | None = None,
) -> None:
    """Создаёт сообщение о результате операции.

    Сообщение будет показано вверху текущей вкладки при следующем вызове
    render_messages() и будет держаться до закрытия пользователем.

    Args:
        level: Уровень сообщения ("success", "warning", "error", "info")
        title: Заголовок сообщения
        stats: Словарь со статистикой (опционально)
        details: Список строк с подробностями (опционально)

    Examples:
        report("success", "Документ сохранён", {"id": 123})
        report("error", "Не удалось сохранить", details=["Нет доступа к БД"])
    """
    # Получаем имя текущей вкладки из session_state
    tab = st.session_state.get("_last_active_tab", "")
    _push_message(tab, level, title, stats, details)


def report_batch(title_ok: str, ok: int, total: int, errors: list[str]) -> None:
    """Создаёт сообщение об итоге массовой операции.

    Автоматически определяет уровень по соотношению ok/total и формирует
    заголовок вида "Операция: N из M".

    Args:
        title_ok: Название операции (например, "Удалено", "Опубликовано")
        ok: Число успешных операций
        total: Общее число операций
        errors: Список ошибок (строки с описанием)

    Examples:
        report_batch("Опубликовано", 5, 8, ["Документ А: нет доступа", "Документ Б: ошибка API"])
    """
    level = outcome_level(ok, total)
    title = f"{title_ok}: {ok} из {total}"
    tab = st.session_state.get("_last_active_tab", "")
    _push_message(tab, level, title, None, errors)


def _push_toast(message: str, icon: str) -> None:
    """Добавляет toast в очередь (внутренняя функция).

    Args:
        message: Текст сообщения
        icon: Иконка (эмодзи)
    """
    if "_notify_toasts" not in st.session_state:
        st.session_state["_notify_toasts"] = []

    st.session_state["_notify_toasts"].append({
        "id": str(uuid.uuid4()),
        "message": message,
        "icon": icon,
    })


def _pop_toasts() -> list[dict[str, str]]:
    """Извлекает все toasts из очереди и очищает её (внутренняя функция).

    Returns:
        Список словарей с ключами "message" и "icon"
    """
    if "_notify_toasts" not in st.session_state:
        return []

    toasts = st.session_state["_notify_toasts"]
    st.session_state["_notify_toasts"] = []
    return toasts


def toast(message: str, icon: str = "✅") -> None:
    """Создаёт короткое подтверждение без подробностей.

    Используется только для успешного результата одного простого действия
    без статистики и подробностей. Любые предупреждения, ошибки, массовые
    операции, сводки — только баннером через report/report_batch.

    Args:
        message: Короткий текст (например, "Сохранено", "Удалено", "Скопировано")
        icon: Иконка (эмодзи), по умолчанию ✅

    Examples:
        toast("Сохранено")
        toast("Скопировано в буфер", "📋")
    """
    _push_toast(message, icon)


def render_messages(tab: str) -> None:
    """Отрисовывает все сообщения для указанной вкладки.

    Должна вызываться в начале каждой вкладки (через slot в app.py).
    Показывает баннеры с результатами операций и toasts.

    Args:
        tab: Имя вкладки
    """
    if "_notify" not in st.session_state:
        st.session_state["_notify"] = []

    messages = [m for m in st.session_state["_notify"] if m["tab"] == tab]

    # Отрисовка баннеров
    if messages:
        # Если больше одного сообщения — кнопка "Закрыть все"
        if len(messages) > 1:
            if st.button("Закрыть все сообщения", key=f"notify_close_all_{tab}"):
                st.session_state["_notify"] = [
                    m for m in st.session_state["_notify"] if m["tab"] != tab
                ]
                st.rerun()

        for msg in messages:
            _render_single_message(msg)

    # Отрисовка toasts
    toasts = _pop_toasts()
    for t in toasts:
        st.toast(t["message"], icon=t["icon"])


def _render_single_message(msg: dict) -> None:
    """Отрисовывает одно сообщение (внутренняя функция).

    Args:
        msg: Словарь с ключами id, level, title, stats, details
    """
    level = msg["level"]
    title = msg["title"]
    stats = msg["stats"]
    details = msg["details"]
    msg_id = msg["id"]

    # Выбор функции Streamlit по уровню
    st_func = getattr(st, level)

    # Формирование содержимого сообщения
    content = f"**{title}**"

    stats_line = format_stats(stats)
    if stats_line:
        content += f"\n\n{stats_line}"

    # Создаём контейнер для сообщения и кнопки закрытия
    col1, col2 = st.columns([0.95, 0.05])

    with col1:
        st_func(content)

        # Подробности в раскрываемом блоке
        if details:
            with st.expander("Подробности"):
                for detail in details:
                    st.text(detail)

    with col2:
        if st.button("✕", key=f"notify_close_{msg_id}"):
            _dismiss_message(msg_id)
            st.rerun()

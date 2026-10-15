"""Единый вывод сообщений о результатах операций (issue #366).

Сообщения — всплывающие окна справа сверху видимой области, переживают
st.rerun(), закрываются ✕ или гаснут сами через 20 с. Цвет по исходу: зелёный (всё ок), жёлтый (частично),
красный (ошибка), синий (информация).
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
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
        "ts": time.time(),
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


TTL = 20  # секунд до автоскрытия

_CSS = """
.st-key-ntfstack{position:fixed;top:60px;right:16px;width:min(340px,calc(100vw - 32px));z-index:999995;
 display:flex;flex-direction:column;gap:6px;pointer-events:none}
.st-key-ntfstack{flex:none !important;height:auto !important}
.st-key-ntfstack > [data-testid="stLayoutWrapper"]{flex:0 0 auto !important;height:auto !important;min-height:0 !important}
[class*="st-key-ntf_"]{position:relative;pointer-events:auto;overflow:hidden;border-radius:8px;
 display:block !important;flex:0 0 auto !important;height:auto !important;min-height:0 !important;padding:7px 30px 7px 12px !important;font-size:13px;line-height:1.45;word-break:break-word;
 border-left:4px solid;box-shadow:0 2px 10px rgba(0,0,0,.25);animation:ntfout 20s linear forwards}
[class*="st-key-ntf_"] [data-testid="stElementContainer"],[class*="st-key-ntf_"] [data-testid="stMarkdown"],[class*="st-key-ntf_"] [data-testid="stMarkdownContainer"]{height:auto !important;min-height:0 !important;flex:0 0 auto !important}
[class*="st-key-ntf_"] [data-testid="stMarkdown"],[class*="st-key-ntf_"] [data-testid="stMarkdownContainer"],[class*="st-key-ntf_"] [data-testid="stElementContainer"]{margin:0 !important}
[class*="st-key-ntf_"] [data-testid="stMarkdown"] > div{display:block !important;height:auto !important;min-height:0 !important;margin:0 !important}
[class*="st-key-ntf_"] [data-testid="stMarkdownContainer"]{font-size:13px !important;line-height:1.45 !important}
[class*="st-key-ntf_"] p,[class*="st-key-ntf_"] summary,[class*="st-key-ntf_"] pre{margin:0 !important;font-size:13px !important;color:inherit !important}
[class*="st-key-ntf_"] [data-testid="stElementContainer"]:has(button){position:absolute;top:0;right:2px;width:auto !important}
[class*="st-key-ntf_"] button{min-height:0 !important;padding:0 6px !important;border:0 !important;background:transparent !important;
 font-size:13px !important;line-height:1.5 !important;color:inherit !important}
[class*="st-key-ntf_success_"]{background:#e6f4ea;color:#0b3d1a;border-color:#2e9e4f}
[class*="st-key-ntf_warning_"]{background:#f7e3a1;color:#4a3800;border-color:#b8860b}
[class*="st-key-ntf_error_"]{background:#f9d6d5;color:#6b1111;border-color:#d93025}
[class*="st-key-ntf_info_"]{background:#e8f0fe;color:#0f2f66;border-color:#1a73e8}
@keyframes ntfout{0%,97%{opacity:1;max-height:600px}100%{opacity:0;max-height:0;padding:0;visibility:hidden}}
@keyframes ntfspin{to{transform:rotate(360deg)}}
.ntf-busy{display:flex;align-items:center;gap:8px;font-size:12px;opacity:.8;margin:2px 0}
.ntf-busy i{width:14px;height:14px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;
 display:inline-block;animation:ntfspin .8s linear infinite}
"""

_ICONS = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}


def render_messages(tab: str) -> None:
    """Показывает сообщения вкладки всплывающими окнами справа сверху видимой области.

    Окно — position: fixed, мелкий шрифт, крестик закрытия, автоскрытие через
    TTL секунд (CSS-анимация; просроченные удаляются из session_state).

    Args:
        tab: Имя вкладки
    """
    for t in _pop_toasts():
        _push_message(tab, "success", f"{t['icon']} {t['message']}", None, None)

    now = time.time()
    msgs = [m for m in st.session_state.get("_notify", []) if now - m.get("ts", now) < TTL]
    st.session_state["_notify"] = msgs
    shown = [m for m in msgs if m["tab"] == tab]
    if not shown:
        return

    css = _CSS + "".join(
        f'.st-key-ntf_{m["level"]}_{m["id"].replace("-", "")}{{animation-delay:-{now - m.get("ts", now):.1f}s}}'
        for m in shown
    )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    with st.container(key="ntfstack"):
        for m in shown:
            with st.container(key=f'ntf_{m["level"]}_{m["id"].replace("-", "")}'):
                text = m["title"]
                stats_line = format_stats(m["stats"])
                if stats_line:
                    text += f" — {stats_line}"
                st.markdown(text)
                if m["details"]:
                    with st.expander("Подробности"):
                        for d in m["details"]:
                            st.text(d)
                st.button("✕", key=f'ntfx_{m["id"]}', on_click=_dismiss_message, args=(m["id"],))


@contextmanager
def busy(text: str):
    """Индикатор выполнения с крутящейся иконкой (вместо st.spinner) на месте вызова.

    Args:
        text: Текст, например "Генерация 5 изобр. (~6 с/шт)…"
    """
    ph = st.empty()
    ph.markdown(f"<style>{_CSS}</style><div class='ntf-busy'><i></i><span>{text}</span></div>",
                unsafe_allow_html=True)
    try:
        yield
    finally:
        ph.empty()


def install() -> None:
    """Перенаправляет st.success/error/warning/toast во всплывающие сообщения (идемпотентно)."""
    if getattr(st, "_ntf_patched", False):
        return

    def mk(level: Level):
        def f(body="", *args, icon=None, **kwargs):
            report(level, str(body))
        return f

    def t(body="", *args, icon=None, **kwargs):
        toast(str(body), icon or "✅")

    st.success, st.error, st.warning, st.toast = mk("success"), mk("error"), mk("warning"), t
    st._ntf_patched = True

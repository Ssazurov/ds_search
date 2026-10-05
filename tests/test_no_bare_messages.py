"""Охранный тест: запрет прямых вызовов st.success/error/warning/info в ui/*.py (#372).

Все результаты операций должны выводиться через notify.report/report_batch/toast.
Прямые вызовы st.success/error/warning/info допустимы только для:
- Пустых состояний (нет данных для отображения)
- Подсказок пользователю о невыполненных условиях
- Статусов фоновых процессов (пересборка, агенты)

Все исключения явно перечислены в ALLOWED с комментариями о причине.
"""
import re
from pathlib import Path

# Допустимые использования прямых вызовов (с обоснованием)
ALLOWED = {
    'ui/agents_status_tab.py::st.info("Search-runs ещё не запускались")': 'Пустое состояние: нет данных агентов',
    'ui/agents_status_tab.py::st.info("Источников пока нет")': 'Пустое состояние: нет данных агентов',
    'ui/agents_status_tab.py::st.info("Новостей пока нет")': 'Пустое состояние: нет данных агентов',
    'ui/dashboard_tab.py::st.info("Ошибок нет")': 'Пустое состояние: ошибок нет',
    'ui/news_tab.py::st.warning("Текст оригинала не сохранён — сравнить': 'Пустое состояние / подсказка / подтверждение / инлайн-предупреждение',
    'ui/news_tab.py::st.warning(f"Перекрытие {ov[\'ratio\']:.0%} выше ори': 'Пустое состояние / подсказка / подтверждение / инлайн-предупреждение',
    'ui/news_tab.py::st.success("Очередь пересказов пуста")': 'Пустое состояние / подсказка / подтверждение / инлайн-предупреждение',
    'ui/news_tab.py::st.info("Нет новостей по выбранному фильтру")': 'Пустое состояние / подсказка / подтверждение / инлайн-предупреждение',
    'ui/news_tab.py::st.warning(f"Удалить везде: {len(selected)} шт.? З': 'Пустое состояние / подсказка / подтверждение / инлайн-предупреждение',
    'ui/news_tab.py::st.info("Выберите одну запись в таблице, чтобы отк': 'Пустое состояние / подсказка / подтверждение / инлайн-предупреждение',
    'ui/results_tab.py::st.info("Ничего не найдено по текущим фильтрам")': 'Пустое состояние: ничего не найдено',
    'ui/search_tab.py::st.warning("Дата «От» позже даты «До» — результато': 'Inline подсказка: даты выбраны некорректно',
    'ui/site_publish_tab.py::st.info("Пересборка ещё не запускалась.")': 'Статус фонового процесса (пересборка сайта)',
    'ui/site_publish_tab.py::st.warning(f"Идёт {kind} (старт {when}) — нажмите ': 'Статус фонового процесса (пересборка сайта)',
    'ui/site_publish_tab.py::st.success(f"Готово: {kind}, старт {when}." + (f" ': 'Статус фонового процесса (пересборка сайта)',
    'ui/site_publish_tab.py::st.error(f"{kind.capitalize()} завершилась с ошибк': 'Статус фонового процесса (пересборка сайта)',
    'ui/sources_tab.py::st.info("Доменов пока нет")': 'Пустое состояние: доменов нет',
    'ui/upload_tab.py::st.info("Очередь пуста")': 'Пустое состояние: очередь пуста',
}


def test_no_bare_streamlit_messages():
    """Проверяет отсутствие прямых вызовов st.success/error/warning/info в ui/*.

    Ищет паттерны st.success(, st.error(, st.warning(, st.info( во всех ui/*.py
    кроме notify.py. Все найденные вызовы должны быть в ALLOWED, иначе тест падает
    со списком нарушений в формате 'файл:строка' (ключ ALLOWED — файл::начало строки, устойчив к сдвигу номеров).
    """
    ui_dir = Path(__file__).parent.parent / "ui"
    pattern = re.compile(r"\bst\.(success|error|warning|info)\s*\(")
    
    violations = []
    
    for py_file in ui_dir.glob("*.py"):
        # Пропускаем notify.py — он содержит notify.report и внутри использует st.*
        if py_file.name == "notify.py":
            continue
        
        content = py_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        for line_num, line in enumerate(lines, start=1):
            if pattern.search(line):
                location = f"ui/{py_file.name}::{line.strip()[:50]}"
                if location not in ALLOWED:
                    violations.append(f"{py_file.name}:{line_num}: {line.strip()}")
    
    if violations:
        msg = (
            "Найдены прямые вызовы st.success/error/warning/info.\n"
            "Все результаты операций должны выводиться через notify.report/report_batch/toast.\n"
            "Если вызов допустим (пустое состояние, подсказка, статус процесса) — "
            "добавьте его в ALLOWED с комментарием.\n\n"
            "Нарушения:\n" + "\n".join(violations)
        )
        raise AssertionError(msg)

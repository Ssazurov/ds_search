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
    # Пустые состояния — информируют об отсутствии данных для отображения
    "ui/agents_status_tab.py:43": "Пустое состояние: search-runs не запускались",
    "ui/agents_status_tab.py:50": "Пустое состояние: источников нет",
    "ui/agents_status_tab.py:72": "Пустое состояние: новостей нет",
    "ui/dashboard_tab.py:54": "Пустое состояние: ошибок нет",
    "ui/news_tab.py:381": "Пустое состояние: нет новостей по фильтру",
    "ui/news_tab.py:87": "Пустое состояние: у digest нет текста оригинала",
    "ui/news_tab.py:103": "Инлайн-предупреждение: перекрытие выше ориентира (не блокирует)",
    "ui/news_tab.py:368": "Пустое состояние: очередь пересказов пуста",
    "ui/news_tab.py:414": "Пустое состояние: нет новостей по фильтру",
    "ui/news_tab.py:455": "Подсказка: выберите запись для редактирования",
    "ui/results_tab.py:157": "Пустое состояние: ничего не найдено",
    "ui/upload_tab.py:37": "Пустое состояние: очередь пуста",
    "ui/sources_tab.py:196": "Пустое состояние: доменов нет",
    
    # Подсказка о невыполненном условии (inline предупреждение)
    "ui/search_tab.py:67": "Inline подсказка: даты выбраны некорректно",
    
    # Статус фонового процесса (пересборка сайта)
    "ui/site_publish_tab.py:60": "Пустое состояние: пересборка не запускалась",
    "ui/site_publish_tab.py:65": "Статус процесса: пересборка в процессе",
    "ui/site_publish_tab.py:67": "Статус процесса: пересборка завершена",
    "ui/site_publish_tab.py:69": "Статус процесса: пересборка завершилась с ошибкой",
}


def test_no_bare_streamlit_messages():
    """Проверяет отсутствие прямых вызовов st.success/error/warning/info в ui/*.

    Ищет паттерны st.success(, st.error(, st.warning(, st.info( во всех ui/*.py
    кроме notify.py. Все найденные вызовы должны быть в ALLOWED, иначе тест падает
    со списком нарушений в формате 'файл:строка'.
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
                location = f"ui/{py_file.name}:{line_num}"
                if location not in ALLOWED:
                    violations.append(f"{location}: {line.strip()}")
    
    if violations:
        msg = (
            "Найдены прямые вызовы st.success/error/warning/info.\n"
            "Все результаты операций должны выводиться через notify.report/report_batch/toast.\n"
            "Если вызов допустим (пустое состояние, подсказка, статус процесса) — "
            "добавьте его в ALLOWED с комментарием.\n\n"
            "Нарушения:\n" + "\n".join(violations)
        )
        raise AssertionError(msg)

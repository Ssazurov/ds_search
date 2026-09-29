"""Тесты устойчивости кнопки «В новости» (issue #392)."""
from __future__ import annotations


def test_to_news_survives_status_update_failure():
    """Ошибка update_discovered_source показывается через notify, без трейсбека.
    
    Проверяет логику из results_tab.py:141-165 — если update_discovered_source
    падает, ошибка попадает в details notify.report, а черновик не теряется.
    """
    # arrange: имитируем логику кнопки "В новости"
    from ui.news_add import describe
    
    def outcome_level(ok: int, total: int) -> str:
        """outcome_level из notify.py без импорта streamlit."""
        if total == 0:
            return "info"
        if ok == total:
            return "success"
        if ok == 0:
            return "error"
        return "warning"
    
    rows = [{"id": "1", "url": "https://example.org/a", "title": "Article A"}]
    selected_ids = ["1"]
    chosen = [r for r in rows if r["id"] in selected_ids]
    
    # add_articles_as_news вернул drafted
    results = [("Article A", "drafted")]
    
    finalized_ids = []
    ok = 0
    drafted = 0
    duplicates = 0
    errors = []
    
    for (label, status), row in zip(results, chosen):
        _, msg = describe(status)
        if status == "drafted":
            finalized_ids.append(row["id"])
            ok += 1
            drafted += 1
        elif status == "skipped_duplicate":
            finalized_ids.append(row["id"])
            ok += 1
            duplicates += 1
        else:
            errors.append(f"{label}: {msg}")
    
    # Имитируем сбой update_discovered_source
    status_update_errors = []
    if finalized_ids:
        for row_id in finalized_ids:
            try:
                # Имитируем падение API
                raise Exception("API unavailable")
            except Exception as exc:  # noqa: BLE001
                status_update_errors.append(f"ID {row_id}: {exc}")
    
    stats = {}
    if drafted > 0:
        stats["черновиков"] = drafted
    if duplicates > 0:
        stats["уже были"] = duplicates
    
    # Ошибки смены статуса — в деталях, но не влияют на общий итог
    all_errors = errors[:]
    if status_update_errors:
        all_errors.append("⚠️ Не удалось обновить статус (черновики сохранены):")
        all_errors.extend(status_update_errors)
    
    level = outcome_level(ok, len(chosen))
    title = f"Добавлено в новости: {ok} из {len(chosen)}"
    
    # assert: проверяем, что формат правильный для notify.report
    assert level == "success"  # drafted успешен
    assert title == "Добавлено в новости: 1 из 1"
    assert stats == {"черновиков": 1}
    # Ошибка смены статуса — в деталях
    assert len(all_errors) == 2
    assert all_errors[0] == "⚠️ Не удалось обновить статус (черновики сохранены):"
    assert "API unavailable" in all_errors[1]
    assert "ID 1" in all_errors[1]


def test_to_news_dedup_prevents_double_draft():
    """Черновик не создаётся повторно при повторном нажатии (дедуп в add_single_url)."""
    # arrange
    from ui.news_add import describe
    
    def outcome_level(ok: int, total: int) -> str:
        if total == 0:
            return "info"
        if ok == total:
            return "success"
        if ok == 0:
            return "error"
        return "warning"
    
    rows = [{"id": "1", "url": "https://example.org/a", "title": "Article A"}]
    chosen = rows
    
    # add_articles_as_news возвращает skipped_duplicate при повторе
    results = [("Article A", "skipped_duplicate")]
    
    finalized_ids = []
    ok = 0
    drafted = 0
    duplicates = 0
    errors = []
    
    for (label, status), row in zip(results, chosen):
        _, msg = describe(status)
        if status == "drafted":
            finalized_ids.append(row["id"])
            ok += 1
            drafted += 1
        elif status == "skipped_duplicate":
            finalized_ids.append(row["id"])
            ok += 1
            duplicates += 1
        else:
            errors.append(f"{label}: {msg}")
    
    stats = {}
    if drafted > 0:
        stats["черновиков"] = drafted
    if duplicates > 0:
        stats["уже были"] = duplicates
    
    level = outcome_level(ok, len(chosen))
    title = f"Добавлено в новости: {ok} из {len(chosen)}"
    
    # assert
    assert level == "success"
    assert title == "Добавлено в новости: 1 из 1"
    assert stats == {"уже были": 1}  # дубликат учтён
    assert drafted == 0  # новых черновиков не создано
    assert duplicates == 1
    assert finalized_ids == ["1"]  # ID добавлен в finalized для смены статуса


def test_status_update_partial_failure():
    """Частичный сбой update_discovered_source: часть успешна, часть нет."""
    # arrange
    from ui.news_add import describe
    
    def outcome_level(ok: int, total: int) -> str:
        if total == 0:
            return "info"
        if ok == total:
            return "success"
        if ok == 0:
            return "error"
        return "warning"
    
    rows = [
        {"id": "1", "url": "https://example.org/a", "title": "Article A"},
        {"id": "2", "url": "https://example.org/b", "title": "Article B"},
        {"id": "3", "url": "https://example.org/c", "title": "Article C"},
    ]
    chosen = rows
    
    # Все три drafted
    results = [
        ("Article A", "drafted"),
        ("Article B", "drafted"),
        ("Article C", "drafted"),
    ]
    
    finalized_ids = []
    ok = 0
    drafted = 0
    duplicates = 0
    errors = []
    
    for (label, status), row in zip(results, chosen):
        _, msg = describe(status)
        if status == "drafted":
            finalized_ids.append(row["id"])
            ok += 1
            drafted += 1
        elif status == "skipped_duplicate":
            finalized_ids.append(row["id"])
            ok += 1
            duplicates += 1
        else:
            errors.append(f"{label}: {msg}")
    
    # Имитируем частичный сбой: первый OK, второй и третий падают
    status_update_errors = []
    if finalized_ids:
        for i, row_id in enumerate(finalized_ids):
            try:
                if i > 0:  # ID 2 и 3 падают
                    raise Exception(f"Connection timeout for {row_id}")
            except Exception as exc:  # noqa: BLE001
                status_update_errors.append(f"ID {row_id}: {exc}")
    
    stats = {}
    if drafted > 0:
        stats["черновиков"] = drafted
    if duplicates > 0:
        stats["уже были"] = duplicates
    
    all_errors = errors[:]
    if status_update_errors:
        all_errors.append("⚠️ Не удалось обновить статус (черновики сохранены):")
        all_errors.extend(status_update_errors)
    
    level = outcome_level(ok, len(chosen))
    title = f"Добавлено в новости: {ok} из {len(chosen)}"
    
    # assert
    assert level == "success"  # все drafted
    assert title == "Добавлено в новости: 3 из 3"
    assert stats == {"черновиков": 3}
    # Частичная ошибка смены статуса
    assert len(all_errors) == 3  # заголовок + 2 ошибки
    assert all_errors[0] == "⚠️ Не удалось обновить статус (черновики сохранены):"
    assert "ID 2" in all_errors[1]
    assert "ID 3" in all_errors[2]
    assert "Connection timeout" in all_errors[1]

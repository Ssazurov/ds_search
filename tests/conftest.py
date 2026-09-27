

import pytest as _pytest  # noqa: E402


class _NullRegistryStore:
    """Тестовый двойник реестра источников: не ходит в GAR (герметичность
    тестов). Тестам, которым нужны конкретные записи, передают
    registry_store=... явно в check_license (см. test_registry_store.py,
    test_license_checker.py). Заменяет удалённый SOURCE_REGISTRY_BACKEND=yaml
    (#329, ds ADR-0021)."""

    def get(self, domain):
        return None

    def ensure(self, domain, attribution_template=""):
        return {
            "status": "pending_manual_review",
            "attribution_template": attribution_template,
            "notes": "",
            "publish_permission": "not_set",
        }


@_pytest.fixture(autouse=True)
def _no_gar_registry_by_default(monkeypatch):
    """Тесты герметичны: по умолчанию check_license не ходит в реальный GAR."""
    from src.license import checker

    monkeypatch.setattr(checker, "GarRegistryStore", lambda *a, **k: _NullRegistryStore())

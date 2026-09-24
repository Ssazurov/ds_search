

import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True)
def _registry_backend_yaml(monkeypatch):
    """Тесты герметичны: реестр источников — yaml (не ходим в GAR; ds ADR-0021)."""
    monkeypatch.setenv("SOURCE_REGISTRY_BACKEND", "yaml")

"""issue #184: неизвестный домен должен автоматически получать статус
pending_manual_review в реестре источников (GAR, ds ADR-0021, #329)."""
from unittest.mock import patch

from src.license.checker import LicenseStatus, PublishPermission, check_license


class FakeStore:
    """Минимальный двойник GarRegistryStore для check_license (get/ensure)."""

    def __init__(self, entries=None):
        self.entries = dict(entries or {})
        self.ensured = []

    def get(self, domain):
        return self.entries.get(domain)

    def ensure(self, domain, attribution_template=""):
        entry = {
            "status": "pending_manual_review",
            "attribution_template": attribution_template,
            "notes": "",
            "publish_permission": "not_set",
        }
        self.entries.setdefault(domain, entry)
        self.ensured.append(domain)
        return entry


def _check(store, domain, url=None):
    with patch("src.license.checker._check_robots", return_value=None):
        return check_license(domain, url or f"https://{domain}/", registry_store=store)


def test_unknown_domain_is_persisted_as_pending():
    store = FakeStore({"existing.example": {"status": "allow"}})
    result = _check(store, "new.example")
    assert result.status is LicenseStatus.PENDING_MANUAL_REVIEW
    assert store.entries["new.example"]["status"] == "pending_manual_review"
    assert store.entries["existing.example"]["status"] == "allow"  # существующие записи не тронуты


def test_second_call_does_not_overwrite_manual_edit():
    store = FakeStore()
    _check(store, "new.example")
    # кто-то вручную проставил статус между вызовами
    store.entries["new.example"]["status"] = "deny"
    result = _check(store, "new.example")
    assert result.status is LicenseStatus.DENY
    assert store.ensured == ["new.example"]  # повторно не создавалась


def test_normalize_domain():
    from src.license.checker import normalize_domain

    assert normalize_domain("WWW.Example.org") == "example.org"
    assert normalize_domain("www.example.org:8080") == "example.org"
    assert normalize_domain("https://www.example.org/a/b") == "example.org"
    assert normalize_domain("news.un.org") == "news.un.org"


def test_pending_registered_under_normalized_key():
    """issue #206: домен нормализуется (без www) до обращения к реестру."""
    store = FakeStore()
    _check(store, "www.new.example", "https://www.new.example/")
    assert store.ensured == ["new.example"]


def test_publish_permission_defaults_to_not_set_for_legacy_entry():
    """issue #224: старая запись реестра без поля мигрирует в not_set."""
    store = FakeStore({"legacy.org": {"status": "allow", "notes": ""}})
    result = _check(store, "legacy.org")
    assert result.status == LicenseStatus.ALLOW
    assert result.publish_permission == PublishPermission.NOT_SET


def test_publish_permission_read_and_independent_of_status():
    store = FakeStore({"a.org": {"status": "deny", "publish_permission": "granted"}})
    result = _check(store, "a.org")
    assert result.status == LicenseStatus.DENY
    assert result.publish_permission == PublishPermission.GRANTED


def test_new_domain_registered_with_not_set_permission():
    store = FakeStore()
    _check(store, "new.org")
    assert store.entries["new.org"]["publish_permission"] == "not_set"


def test_parse_publish_permission_unknown_value():
    from src.license.checker import parse_publish_permission

    assert parse_publish_permission("bogus") == PublishPermission.NOT_SET
    assert parse_publish_permission(None) == PublishPermission.NOT_SET
    assert parse_publish_permission("denied") == PublishPermission.DENIED

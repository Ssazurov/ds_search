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
    assert normalize_domain("https://www.example.org/a/b") == "example.org/a/b"
    assert normalize_domain("https://www.example.org/a/b/") == "example.org/a/b"
    assert normalize_domain("news.un.org") == "news.un.org"


class _DictStore:
    """Двойник GarRegistryStore: get/ensure по ключу (issue #473)."""

    def __init__(self, entries=None):
        self.entries = dict(entries or {})
        self.ensured = []

    def get(self, key):
        return self.entries.get(key)

    def ensure(self, key, template=""):
        self.ensured.append(key)
        return None


def _check_key(store, domain):
    from unittest.mock import patch

    from src.license.checker import check_license

    with patch("src.license.checker._check_robots", return_value=None):
        return check_license(domain, f"https://{domain}/", registry_store=store)


def test_path_key_found_by_full_key():
    store = _DictStore({
        "vk.ru/sundetiekb": {"status": "allow", "notes": "ok", "attribution_template": None},
        "vk.ru": {"status": "deny", "notes": "домен", "attribution_template": None},
    })
    result = _check_key(store, "https://www.vk.ru/sundetiekb/")
    assert result.status is LicenseStatus.ALLOW
    assert store.ensured == []


def test_path_key_falls_back_to_domain():
    store = _DictStore({"vk.ru": {"status": "attribution_required", "notes": "d",
                                  "attribution_template": "Источник: {title} ({source_url})"}})
    result = _check_key(store, "vk.ru/other-group")
    assert result.status is LicenseStatus.ATTRIBUTION_REQUIRED
    assert store.ensured == []


def test_unknown_path_key_ensures_full_key_not_domain():
    store = _DictStore()
    result = _check_key(store, "vk.ru/new-group")
    assert result.status is LicenseStatus.PENDING_MANUAL_REVIEW
    assert store.ensured == ["vk.ru/new-group"]


def test_legacy_entry_without_source_type_works():
    store = _DictStore({"vk.ru/sundetiekb": {"status": "allow", "notes": "", "attribution_template": None,
                                             "publish_permission": "not_set"}})
    result = _check_key(store, "vk.ru/sundetiekb")
    assert result.status is LicenseStatus.ALLOW
    assert result.downloadable


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

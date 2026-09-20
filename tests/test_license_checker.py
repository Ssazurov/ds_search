"""issue #184: неизвестный домен должен автоматически появляться в
config/licenses.yaml со статусом pending_manual_review."""
from unittest.mock import patch

import yaml

from src.license.checker import LicenseStatus, check_license


def test_unknown_domain_is_persisted_as_pending(tmp_path):
    registry_path = tmp_path / "licenses.yaml"
    registry_path.write_text("existing.example: {status: allow}\n", encoding="utf-8")

    with patch("src.license.checker._check_robots", return_value=None):
        result = check_license("new.example", "https://new.example/", registry_path=registry_path)

    assert result.status is LicenseStatus.PENDING_MANUAL_REVIEW
    saved = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert saved["new.example"]["status"] == "pending_manual_review"
    assert saved["existing.example"]["status"] == "allow"  # существующие записи не тронуты


def test_second_call_does_not_overwrite_manual_edit(tmp_path):
    registry_path = tmp_path / "licenses.yaml"

    with patch("src.license.checker._check_robots", return_value=None):
        check_license("new.example", "https://new.example/", registry_path=registry_path)

    # кто-то вручную проставил статус между вызовами
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry["new.example"]["status"] = "deny"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")

    with patch("src.license.checker._check_robots", return_value=None):
        result = check_license("new.example", "https://new.example/", registry_path=registry_path)

    assert result.status is LicenseStatus.DENY


def test_normalize_domain():
    from src.license.checker import normalize_domain

    assert normalize_domain("WWW.Example.org") == "example.org"
    assert normalize_domain("www.example.org:8080") == "example.org"
    assert normalize_domain("https://www.example.org/a/b") == "example.org"
    assert normalize_domain("news.un.org") == "news.un.org"


def test_www_url_matches_registry_entry_without_www(tmp_path):
    """issue #206: ссылка на www.<домен> проходит гейт по записи <домен>."""
    registry_path = tmp_path / "licenses.yaml"
    registry_path.write_text(
        "pravmir.ru: {status: attribution_required, attribution_template: 'src {title}'}\n",
        encoding="utf-8",
    )

    with patch("src.license.checker._check_robots", return_value=None):
        result = check_license("www.pravmir.ru", "https://www.pravmir.ru/a/", registry_path=registry_path)

    assert result.downloadable
    assert result.status is LicenseStatus.ATTRIBUTION_REQUIRED
    saved = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert list(saved) == ["pravmir.ru"]  # дубль www.* не создан


def test_legacy_www_key_still_matches(tmp_path):
    registry_path = tmp_path / "licenses.yaml"
    registry_path.write_text("www.legacy.example: {status: allow}\n", encoding="utf-8")

    with patch("src.license.checker._check_robots", return_value=None):
        result = check_license("legacy.example", "https://legacy.example/", registry_path=registry_path)

    assert result.status is LicenseStatus.ALLOW


def test_pending_registered_under_normalized_key(tmp_path):
    registry_path = tmp_path / "licenses.yaml"

    with patch("src.license.checker._check_robots", return_value=None):
        check_license("www.new.example", "https://www.new.example/", registry_path=registry_path)

    assert list(yaml.safe_load(registry_path.read_text(encoding="utf-8"))) == ["new.example"]


def test_publish_permission_defaults_to_not_set_for_legacy_entry(tmp_path, monkeypatch):
    """issue #224: старая запись реестра без поля мигрирует в not_set."""
    from src.license import checker

    reg = tmp_path / "licenses.yaml"
    reg.write_text("legacy.org:\n  status: allow\n  notes: ''\n", encoding="utf-8")
    monkeypatch.setattr(checker, "_check_robots", lambda *a, **k: None)
    res = checker.check_license("legacy.org", "https://legacy.org", registry_path=reg)
    assert res.status == checker.LicenseStatus.ALLOW
    assert res.publish_permission == checker.PublishPermission.NOT_SET


def test_publish_permission_read_and_independent_of_status(tmp_path, monkeypatch):
    from src.license import checker

    reg = tmp_path / "licenses.yaml"
    reg.write_text("a.org:\n  status: deny\n  publish_permission: granted\n", encoding="utf-8")
    monkeypatch.setattr(checker, "_check_robots", lambda *a, **k: None)
    res = checker.check_license("a.org", "https://a.org", registry_path=reg)
    assert res.status == checker.LicenseStatus.DENY
    assert res.publish_permission == checker.PublishPermission.GRANTED


def test_new_domain_registered_with_not_set_permission(tmp_path, monkeypatch):
    import yaml
    from src.license import checker

    reg = tmp_path / "licenses.yaml"
    monkeypatch.setattr(checker, "_check_robots", lambda *a, **k: None)
    checker.check_license("new.org", "https://new.org", registry_path=reg)
    assert yaml.safe_load(reg.read_text(encoding="utf-8"))["new.org"]["publish_permission"] == "not_set"


def test_parse_publish_permission_unknown_value():
    from src.license.checker import PublishPermission, parse_publish_permission

    assert parse_publish_permission("bogus") == PublishPermission.NOT_SET
    assert parse_publish_permission(None) == PublishPermission.NOT_SET
    assert parse_publish_permission("denied") == PublishPermission.DENIED

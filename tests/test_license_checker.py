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

"""ds ADR-0021 (#263): реестр источников в GAR + кэш + fallback license gate."""
import json
from unittest.mock import patch

import httpx

from src.discovery.gar_client import GarDiscoveryClient, GarDiscoveryClientError
from src.discovery.config import Settings
from src.license.checker import LicenseStatus, PublishPermission, check_license
from src.license.registry_store import GarRegistryStore

ENTRY = {"domain": "foma.ru", "status": "attribution_required", "notes": "ok",
         "attribution_template": "Источник: {title} ({source_url}) -- foma.ru",
         "publish_permission": "granted", "is_aggregator": False}


class FakeClient:
    def __init__(self, entries=None, down=False):
        self.entries = entries or {}
        self.down = down
        self.ensured = []

    def _check(self):
        if self.down:
            raise GarDiscoveryClientError("GAR down")

    def get_source_registry_entry(self, domain):
        self._check()
        return self.entries.get(domain)

    def list_source_registry(self):
        self._check()
        return list(self.entries.values())

    def ensure_source_registry_entry(self, domain, attribution_template=""):
        self._check()
        entry = {"domain": domain, "status": "pending_manual_review", "notes": "",
                 "attribution_template": attribution_template, "publish_permission": "not_set",
                 "is_aggregator": False}
        self.entries.setdefault(domain, entry)
        self.ensured.append(domain)
        return entry


def _check(store, domain="foma.ru"):
    with patch("src.license.checker._check_robots", return_value=None):
        return check_license(domain, f"https://{domain}/", registry_store=store)


def test_known_domain_from_gar_and_cache_written(tmp_path):
    cache = tmp_path / "cache.json"
    result = _check(GarRegistryStore(FakeClient({"foma.ru": ENTRY}), cache))
    assert result.status is LicenseStatus.ATTRIBUTION_REQUIRED
    assert result.publish_permission is PublishPermission.GRANTED
    assert json.loads(cache.read_text(encoding="utf-8"))["entries"]["foma.ru"]["status"] == "attribution_required"


def test_gar_down_uses_cache(tmp_path):
    cache = tmp_path / "cache.json"
    _check(GarRegistryStore(FakeClient({"foma.ru": ENTRY}), cache))  # прогрев кэша
    result = _check(GarRegistryStore(FakeClient(down=True), cache))
    assert result.status is LicenseStatus.ATTRIBUTION_REQUIRED
    assert result.downloadable


def test_gar_down_no_cache_is_pending_and_no_exception(tmp_path):
    result = _check(GarRegistryStore(FakeClient(down=True), tmp_path / "none.json"))
    assert result.status is LicenseStatus.PENDING_MANUAL_REVIEW
    assert not result.downloadable


def test_unknown_domain_calls_ensure_pending(tmp_path):
    client = FakeClient()
    result = _check(GarRegistryStore(client, tmp_path / "cache.json"), "new.example")
    assert result.status is LicenseStatus.PENDING_MANUAL_REVIEW
    assert client.ensured == ["new.example"]


def test_existing_entry_never_ensured(tmp_path):
    client = FakeClient({"foma.ru": ENTRY})
    _check(GarRegistryStore(client, tmp_path / "cache.json"))
    assert client.ensured == []


def test_load_all_falls_back_to_cache(tmp_path):
    cache = tmp_path / "cache.json"
    assert GarRegistryStore(FakeClient({"foma.ru": ENTRY}), cache).load_all() == {"foma.ru": ENTRY}
    assert GarRegistryStore(FakeClient(down=True), cache).load_all() == {"foma.ru": ENTRY}


def test_client_registry_methods_use_expected_routes():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/source-registry/missing.ru":
            return httpx.Response(404, json={"detail": "x"})
        if request.url.path.endswith("/ensure"):
            return httpx.Response(201, json=ENTRY)
        return httpx.Response(200, json=ENTRY)

    settings = Settings("http://gar", None, "u", 5.0, 1, 1.0)
    client = GarDiscoveryClient(settings)
    client._client = httpx.Client(base_url="http://gar", transport=httpx.MockTransport(handler))
    assert client.get_source_registry_entry("missing.ru") is None
    assert client.ensure_source_registry_entry("foma.ru", "t")["domain"] == "foma.ru"
    client.put_source_registry_entry("foma.ru", status="allow")
    assert ("POST", "/source-registry/foma.ru/ensure") in seen
    assert ("PUT", "/source-registry/foma.ru") in seen

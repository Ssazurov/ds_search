import pytest

from src.site_publish.permissions import set_publish_permission


class FakeStore:
    def __init__(self, entries=None):
        self.entries, self.put_calls = entries or {}, []

    def get(self, d):
        return self.entries.get(d)

    def ensure(self, d):
        self.entries[d] = {"domain": d, "status": "pending_manual_review"}
        return self.entries[d]

    def put(self, d, e):
        self.put_calls.append((d, e))
        self.entries[d] = e
        return e


def test_sets_permission_keeps_other_fields():
    s = FakeStore({"a.ru": {"domain": "a.ru", "status": "allowed", "notes": "x"}})
    set_publish_permission("A.ru ", "granted", s)
    assert s.put_calls == [("a.ru", {"domain": "a.ru", "status": "allowed", "notes": "x", "publish_permission": "granted"})]


def test_creates_stub_when_missing():
    s = FakeStore()
    set_publish_permission("b.ru", "not_required", s)
    assert s.entries["b.ru"]["publish_permission"] == "not_required"
    assert s.entries["b.ru"]["status"] == "pending_manual_review"


def test_rejects_bad_value_and_empty_domain():
    s = FakeStore()
    with pytest.raises(ValueError):
        set_publish_permission("a.ru", "yes", s)
    with pytest.raises(ValueError):
        set_publish_permission(" ", "granted", s)
    assert s.put_calls == []

"""ds ADR-0021 (#263): фасад load_registry/save_entry/delete_entry всегда
использует GarRegistryStore (yaml legacy убран в #329)."""
from src.license import registry_store as rs


def test_facade_uses_gar_store(monkeypatch):
    calls = []

    class Fake:
        def put(self, d, e):
            calls.append(("put", d, e))

        def delete(self, d):
            calls.append(("del", d))

        def load_all(self):
            return {"x.ru": {"status": "deny"}}

    monkeypatch.setattr(rs, "GarRegistryStore", Fake)
    rs.save_entry("x.ru", {"status": "deny"})
    rs.delete_entry("x.ru")
    assert rs.load_registry() == {"x.ru": {"status": "deny"}}
    assert calls == [("put", "x.ru", {"status": "deny"}), ("del", "x.ru")]

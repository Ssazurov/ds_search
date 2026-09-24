from src.license import registry_store as rs


def test_yaml_roundtrip(tmp_path):
    p = tmp_path / "l.yaml"
    rs.save_entry("a.ru", {"status": "deny"}, p)
    rs.save_entry("b.ru", {"status": "allow"}, p)
    rs.delete_entry("a.ru", p)
    assert rs.load_registry(p) == {"b.ru": {"status": "allow"}}


def test_gar_backend_uses_store(monkeypatch):
    calls = []

    class Fake:
        def put(self, d, e):
            calls.append(("put", d, e))

        def delete(self, d):
            calls.append(("del", d))

        def load_all(self):
            return {"x.ru": {"status": "deny"}}

    monkeypatch.setenv("SOURCE_REGISTRY_BACKEND", "gar")
    monkeypatch.setattr(rs, "GarRegistryStore", Fake)
    rs.save_entry("x.ru", {"status": "deny"})
    rs.delete_entry("x.ru")
    assert rs.load_registry() == {"x.ru": {"status": "deny"}}
    assert calls == [("put", "x.ru", {"status": "deny"}), ("del", "x.ru")]

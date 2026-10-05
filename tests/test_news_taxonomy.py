from src.news import taxonomy


def _items():
    return [{"id": 1, "title": "a", "gar_document_id": "g1"}, {"id": 2, "title": "b", "gar_document_id": None}]


def test_apply_patches_gar_then_db(monkeypatch):
    monkeypatch.setattr(taxonomy, "validate", lambda d, c: None)
    patched, saved = [], []
    monkeypatch.setattr(taxonomy.db, "update_news_item", lambda i, f: saved.append((i, f)))
    ok, errors = taxonomy.apply_taxonomy(_items(), "d", "c", patch_fn=lambda g, u: patched.append((g, u)))
    assert (ok, errors) == (2, [])
    assert patched == [("g1", {"direction": "d", "category": "c"})]
    assert [s[0] for s in saved] == [1, 2]


def test_gar_error_keeps_local_unchanged(monkeypatch):
    monkeypatch.setattr(taxonomy, "validate", lambda d, c: None)
    saved = []
    monkeypatch.setattr(taxonomy.db, "update_news_item", lambda i, f: saved.append(i))

    def boom(g, u):
        raise RuntimeError("422")

    ok, errors = taxonomy.apply_taxonomy(_items(), "d", "", patch_fn=boom)
    assert ok == 1 and len(errors) == 1 and saved == [2]

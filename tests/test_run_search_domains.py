from src.discovery.run_search import _in_domains, normalize_domains


def test_normalize_domains():
    assert normalize_domains("https://www.Example.org/a, foo.ru\nfoo.ru;bar.com:8080") == [
        "example.org", "foo.ru", "bar.com",
    ]
    assert normalize_domains("") == []
    assert normalize_domains(None) == []


def test_in_domains():
    doms = ["example.org"]
    assert _in_domains("https://www.example.org/x", doms)
    assert _in_domains("https://sub.example.org/x", doms)
    assert not _in_domains("https://evil-example.org/x", doms)


def test_normalize_domains_skips_non_domains():
    assert normalize_domains("foma.ru и miloserdie.ru") == ["foma.ru", "miloserdie.ru"]


def test_search_per_domain_filters_and_splits():
    from src.discovery.run_search import _search
    from src.search.base import SearchHit

    class FakeChain:
        def __init__(self):
            self.queries = []

        def search(self, q, max_results=10):
            self.queries.append(q)
            d = q.rsplit("site:", 1)[1]
            return [SearchHit(url=f"https://{d}/a{i}", title="", snippet="") for i in range(3)] + [
                SearchHit(url="https://other.com/x", title="", snippet="")
            ]

    chain = FakeChain()
    hits = _search(chain, "q", ["foma.ru", "miloserdie.ru"], 4)
    assert chain.queries == ["q site:foma.ru", "q site:miloserdie.ru"]
    assert [h.url for h in hits] == [
        "https://foma.ru/a0", "https://foma.ru/a1",
        "https://miloserdie.ru/a0", "https://miloserdie.ru/a1",
    ]

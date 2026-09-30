"""ui/news_add.py — «В новости» из Результатов (issue #351)."""
from ui.news_add import add_articles_as_news, describe


def test_add_articles_collects_statuses_and_survives_errors():
    calls = []

    async def fake_add(url, title=""):
        calls.append((url, title))
        if "bad" in url:
            raise RuntimeError("boom")
        return "drafted" if "ok" in url else "skipped_duplicate"

    res = add_articles_as_news(
        [{"url": "https://a/ok", "title": "A"},
         {"url": "https://a/bad", "title": ""},
         {"url": "https://a/dup", "title": "C"}],
        add=fake_add,
    )
    assert [s for _, s in res][0] == "drafted"
    assert res[1][0] == "https://a/bad" and "boom" in res[1][1]
    assert res[2] == ("C", "skipped_duplicate")
    assert calls[0] == ("https://a/ok", "A")


def test_describe_known_and_unknown():
    assert describe("drafted")[0] == "success"
    assert describe("skipped_duplicate")[0] == "info"
    assert describe("weird") == ("error", "weird")

from ui.news_add import summarize


def test_summarize_mixed():
    out = summarize([("A", "drafted"), ("B", "skipped_duplicate"),
                     ("C", "license_denied"), ("D", "drafted")])
    assert out.finalized == [0, 1, 3]
    assert (out.ok, out.drafted, out.duplicates) == (3, 2, 1)
    assert len(out.errors) == 1 and out.errors[0].startswith("C: ")
    assert out.stats == {"черновиков": 2, "уже были": 1}


def test_summarize_empty():
    out = summarize([])
    assert out.finalized == [] and out.ok == 0 and out.stats == {}

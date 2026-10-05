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


def test_local_meta_passed_to_add():
    from ui.news_add import add_articles_as_news
    calls = []

    async def fake_add(url, title="", **kw):
        calls.append(kw)
        return "drafted"

    add_articles_as_news(
        [{"url": "u1", "title": "t", "local_meta": {"content_path": "/x.md"}}, {"url": "u2"}],
        add=fake_add)
    assert calls[0] == {"local_meta": {"content_path": "/x.md"}}
    assert calls[1] == {}


def test_collect_one_uses_local_content_without_download(tmp_path, monkeypatch):
    import asyncio
    from src.news import collect

    md = tmp_path / "a.md"
    md.write_text("текст поста", encoding="utf-8")

    async def boom(*a, **k):
        raise AssertionError("download_single не должен вызываться")

    monkeypatch.setattr(collect, "download_single", boom)
    monkeypatch.setattr(collect, "generate_draft", lambda src, **k: (_ for _ in ()).throw(RuntimeError("stop")))
    hit = collect.SearchHit(url="https://vk.ru/wall-1_1", title="T", snippet="")
    res = asyncio.run(collect._collect_one(
        hit, None, tmp_path, tmp_path / "db.sqlite", local_meta={"content_path": str(md)}))
    assert res == "llm_failed"  # дошли до LLM, скачивания не было

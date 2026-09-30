"""Тесты UI-логики пересказа: подсветка, чеклист, source_text, формат при добавлении (ds_search#421)."""
import asyncio
from pathlib import Path

from src.news import db, digest_check, overlap
from ui.news_add import add_articles_as_news

SRC = (
    "Фонд открыл в Москве новый центр ранней помощи для детей с синдромом Дауна. "
    "Занятия проводят логопеды и психологи, а родители получают консультации бесплатно. "
    "Центр рассчитан на сто семей в год и работает по будням с девяти до шести."
)
PARAPHRASE = "В столице появился центр, где малыши с трисомией получают помощь специалистов."


def _item(**kw) -> dict:
    base = {
        "format": "digest", "source_url": "https://ex.org/a", "source_name": "ex.org",
        "title": "T", "body_md": PARAPHRASE, "quotes": [],
        "direction": "d", "category": "c", "source_text": SRC,
    }
    base.update(kw)
    return base


def _failed(ev: dict) -> list[str]:
    return [c["label"] for c in ev["checks"] if not c["ok"]]


# --- подсветка ---

def test_highlight_marks_shared_fragment_and_escapes():
    other = "<b>Занятия проводят логопеды и психологи, а родители получают консультации</b>"
    html = overlap.highlight_html(SRC, other)
    assert "<mark>Занятия проводят логопеды и психологи, а родители получают консультации</mark>" in html
    assert "<b>" not in overlap.highlight_html(other, SRC)  # экранирование
    assert "&lt;b&gt;" in overlap.highlight_html(other, SRC)


def test_highlight_no_overlap_has_no_marks():
    assert "<mark>" not in overlap.highlight_html(SRC, PARAPHRASE)


def test_highlight_skips_guillemet_quotes():
    quote = "Занятия проводят логопеды и психологи, а родители получают консультации"
    draft = f"Центр открыт. «{quote}», — сказали в фонде."
    assert "<mark>" in overlap.highlight_html(draft, SRC)
    assert "<mark>" not in overlap.highlight_html(draft, SRC, skip_quotes=True)


# --- чеклист ---

def test_checklist_all_ok():
    ev = digest_check.evaluate(_item())
    assert ev["ok"] and not _failed(ev)
    assert ev["overlap"]["max_run"] < overlap.MAX_RUN_WORDS


def test_checklist_verbatim_run_blocks():
    ev = digest_check.evaluate(_item(body_md=SRC))
    assert not ev["ok"]
    assert any("серии" in label for label in _failed(ev))


def test_checklist_too_many_quotes_blocks():
    ev = digest_check.evaluate(_item(quotes=["а", "б", "в"]))
    assert not ev["ok"] and any("Цитат" in label for label in _failed(ev))


def test_checklist_requires_source_link():
    ev = digest_check.evaluate(_item(source_url="manual:123", source_name="Редакция"))
    assert not ev["ok"] and any("Ссылка" in label for label in _failed(ev))
    # ручной черновик с URL в «Источнике» — ссылка есть
    assert digest_check.evaluate(_item(source_url="manual:123", source_name="https://ex.org/x"))["ok"]


def test_checklist_requires_direction_and_category():
    assert not digest_check.evaluate(_item(direction=None))["ok"]
    assert not digest_check.evaluate(_item(category=""))["ok"]


def test_checklist_without_source_text_blocks():
    ev = digest_check.evaluate(_item(source_text=None))
    assert not ev["ok"] and ev["overlap"] is None


def test_blockers_only_for_digest():
    assert digest_check.blockers(_item(format="news", direction=None)) == []
    assert digest_check.blockers(_item(direction=None)) == ["Направление и категория выбраны"]
    assert digest_check.blockers(_item()) == []


# --- БД ---

def test_db_stores_source_text_for_digest_only(tmp_path: Path):
    p = tmp_path / "n.db"
    db.init_db(p)
    d_id = db.insert_news_item(_item(source_url="https://ex.org/d"), db_path=p)
    n_id = db.insert_news_item(
        {"source_url": "https://ex.org/n", "title": "N", "source_text": SRC}, db_path=p)
    assert db.get_news_item(d_id, p)["source_text"] == SRC
    assert db.get_news_item(n_id, p)["source_text"] is None


def test_update_saves_quotes_and_overlap_metrics(tmp_path: Path):
    p = tmp_path / "n.db"
    db.init_db(p)
    i = db.insert_news_item(_item(), db_path=p)
    db.update_news_item(i, {"quotes": ["q1"], "overlap_max_run": 3, "overlap_ratio": 0.05}, db_path=p)
    row = db.get_news_item(i, p)
    assert row["quotes"] == ["q1"] and row["overlap_max_run"] == 3


# --- формат при добавлении ---

def test_add_articles_passes_fmt_only_for_digest():
    seen = []

    async def fake_add(url, title="", **kw):
        seen.append(kw)
        return "drafted"

    add_articles_as_news([{"url": "https://a/1"}], add=fake_add)
    add_articles_as_news([{"url": "https://a/2"}], add=fake_add, fmt="digest")
    assert seen == [{}, {"fmt": "digest"}]


def test_add_single_url_digest_uses_digest_generation(tmp_path, monkeypatch):
    from src.news import collect

    captured = {}

    def fake_generate(source, config=None, **kw):
        captured.update(kw)
        return _item(source_url=source["source_url"])

    async def fake_download(source, data_root=None):
        f = tmp_path / "a.md"
        f.write_text(SRC, encoding="utf-8")
        return {"content_path": str(f), "source_url": source["url"], "title": "T"}

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", fake_generate)
    p = tmp_path / "n.db"
    res = asyncio.run(collect.add_single_url("https://ex.org/z", db_path=p, fmt="digest", data_root=tmp_path))
    assert res == "drafted"
    assert captured == {"fmt": "digest", "autoclassify": True}
    assert db.list_news_items(db_path=p)[0]["format"] == "digest"

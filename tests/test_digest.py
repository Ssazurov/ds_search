"""Тесты пересказа (digest): overlap, LLM-черновик, БД, публикация (ds_search#420)."""
import json
import sqlite3
from pathlib import Path

import pytest

from src.news import db, llm_draft, overlap, publish
from src.news.llm_draft import LlmConfig, NotRelevantError, generate_draft

SRC = (
    "Фонд открыл в Москве новый центр ранней помощи для детей с синдромом Дауна. "
    "Занятия проводят логопеды и психологи, а родители получают консультации бесплатно. "
    "Центр рассчитан на сто семей в год и работает по будням с девяти до шести."
)


def _cfg(**kw) -> LlmConfig:
    base = dict(
        provider="ollama", model="m", endpoint="http://x", temperature=0.3,
        max_tokens=100, prompt_template="{source_text}",
        prompt_template_digest="D|{source_name}|{source_url}|{source_title}|{source_text}",
        max_tokens_digest=555, num_ctx_digest=4096,
    )
    base.update(kw)
    return LlmConfig(**base)


# --- overlap ---

def test_overlap_verbatim_copy_flagged():
    res = overlap.check_overlap(SRC, SRC)
    assert not res["ok"]
    assert res["max_run"] >= overlap.MAX_RUN_WORDS
    assert res["ratio"] > overlap.MAX_RATIO


def test_overlap_paraphrase_ok():
    draft = "В столице появился центр, где малыши с трисомией получают помощь специалистов."
    res = overlap.check_overlap(SRC, draft)
    assert res["ok"], res


def test_overlap_ignores_guillemet_quotes():
    quote = "Занятия проводят логопеды и психологи, а родители получают консультации бесплатно"
    draft = f"Новый центр заработал. «{quote}», — рассказали в фонде."
    res = overlap.check_overlap(SRC, draft, quotes=[quote])
    assert res["ok"], res


def test_check_quotes_limits():
    long_q = " ".join(["слово"] * 26)
    assert overlap.check_quotes(["а", "б"]) == []
    assert len(overlap.check_quotes(["а", "б", "в"])) == 1
    assert len(overlap.check_quotes([long_q])) == 1


# --- llm_draft ---

def test_build_prompt_digest_uses_digest_template():
    p = llm_draft.build_prompt(_cfg(), {"source_name": "N", "source_url": "U", "title": "T", "text": "X"}, "digest")
    assert p == "D|N|U|T|X"


def test_build_prompt_digest_requires_template():
    with pytest.raises(ValueError):
        llm_draft.build_prompt(_cfg(prompt_template_digest=""), {}, "digest")


def _fake_llm(payload: dict, seen: dict | None = None):
    def _call(prompt, cfg, **kwargs):
        if seen is not None:
            seen["cfg"] = cfg
        return json.dumps(payload, ensure_ascii=False)
    return _call


def test_generate_digest_draft(monkeypatch):
    seen: dict = {}
    payload = {
        "relevant": True, "title": "Новый центр помощи", "summary": "Открылся центр.",
        "body_md": "В столице открылся центр помощи малышам.", "quotes": ["цитата"], "tags": ["сд"],
    }
    monkeypatch.setattr(llm_draft, "call_llm", _fake_llm(payload, seen))
    item = generate_draft(
        {"source_url": "https://ex.org/a", "source_name": "Ex", "title": "T", "text": SRC},
        _cfg(), fmt="digest",
    )
    assert item["format"] == "digest" and item["status"] == "draft"
    assert item["quotes"] == ["цитата"]
    assert item["overlap_max_run"] is not None
    assert seen["cfg"].max_tokens == 555 and seen["cfg"].num_ctx == 4096


def test_generate_digest_not_relevant(monkeypatch):
    monkeypatch.setattr(llm_draft, "call_llm", _fake_llm({"relevant": False, "relevance_reason": "не по теме"}))
    with pytest.raises(NotRelevantError):
        generate_draft({"source_url": "u", "text": SRC}, _cfg(), fmt="digest")


def test_generate_digest_autoclassify(monkeypatch):
    monkeypatch.setattr(llm_draft, "call_llm", _fake_llm({"relevant": True, "title": "T", "body_md": "текст"}))
    monkeypatch.setattr(publish, "classify_item", lambda item: {"direction": "sd", "category": "health", "age": "x"})
    item = generate_draft({"source_url": "u", "text": SRC}, _cfg(), fmt="digest", autoclassify=True)
    assert item["direction"] == "sd" and item["category"] == "health"


def test_generate_unknown_format():
    with pytest.raises(ValueError):
        generate_draft({"source_url": "u", "text": "x"}, _cfg(), fmt="zzz")


# --- db ---

def test_db_digest_roundtrip(tmp_path: Path):
    p = tmp_path / "n.db"
    db.init_db(p)
    item_id = db.insert_news_item(
        {"source_url": "https://ex.org/1", "title": "T", "format": "digest", "quotes": ["q1"],
         "overlap_max_run": 3, "overlap_ratio": 0.05}, p)
    row = db.get_news_item(item_id, p)
    assert row["format"] == "digest" and row["quotes"] == ["q1"]
    assert row["overlap_max_run"] == 3
    db.update_news_item(item_id, {"quotes": ["a", "b"]}, p)
    assert db.get_news_item(item_id, p)["quotes"] == ["a", "b"]


def test_db_default_format_news(tmp_path: Path):
    p = tmp_path / "n.db"
    db.init_db(p)
    item_id = db.insert_news_item({"source_url": "u", "title": "T"}, p)
    row = db.get_news_item(item_id, p)
    assert row["format"] == "news" and row["quotes"] == []


def test_db_invalid_format(tmp_path: Path):
    p = tmp_path / "n.db"
    db.init_db(p)
    with pytest.raises(ValueError):
        db.insert_news_item({"source_url": "u", "title": "T", "format": "zzz"}, p)


def test_db_migrates_legacy(tmp_path: Path):
    p = tmp_path / "old.db"
    conn = sqlite3.connect(p)
    conn.execute(
        "CREATE TABLE news_items (id INTEGER PRIMARY KEY AUTOINCREMENT, source_url TEXT NOT NULL UNIQUE,"
        " source_name TEXT, source_published_at TEXT, title TEXT NOT NULL, summary TEXT, body_md TEXT,"
        " direction TEXT, tags TEXT NOT NULL DEFAULT '[]', requires_review INTEGER NOT NULL DEFAULT 0,"
        " status TEXT NOT NULL DEFAULT 'draft', channels TEXT NOT NULL DEFAULT '[]',"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')), published_at TEXT)")
    conn.execute("INSERT INTO news_items (source_url, title) VALUES ('u', 'T')")
    conn.commit()
    conn.close()
    db.init_db(p)
    row = db.list_news_items(db_path=p)[0]
    assert row["format"] == "news" and row["quotes"] == []


# --- publish ---

def _digest(**kw) -> dict:
    base = {"source_url": "https://www.example.org/a/1", "title": "Пересказ", "body_md": "Текст.",
            "format": "digest", "tags": ["сд"]}
    base.update(kw)
    return base


def test_build_content_md_digest_has_source_block():
    md = publish.build_content_md(_digest())
    assert "Это краткий пересказ" in md
    assert "[example.org](https://www.example.org/a/1)" in md


def test_build_content_md_news_has_no_block():
    md = publish.build_content_md(_digest(format="news"))
    assert "краткий пересказ" not in md


def test_build_content_md_digest_requires_http_url():
    with pytest.raises(ValueError):
        publish.build_content_md(_digest(source_url="manual:abc"))


def test_build_content_md_digest_manual_with_url_in_source_name():
    md = publish.build_content_md(_digest(source_url="manual:abc", source_name="https://site.ru/x"))
    assert "(https://site.ru/x)" in md


def test_build_metadata_doc_type(monkeypatch):
    monkeypatch.setattr(publish, "classify_item", lambda item: {})
    assert publish.build_metadata(_digest())["doc_type"] == "digest"
    assert publish.build_metadata(_digest(format="news"))["doc_type"] == "news"

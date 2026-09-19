"""Тесты src/news/text_clean.py и связанных правок LLM-шага (issue #208)."""
import asyncio

import httpx

from src.news import collect
from src.news.llm_draft import LlmConfig, _call_ollama, load_llm_config
from src.news.text_clean import MAX_CHARS, clean_article_text

_PARA = ("Реализация масштабного социального проекта начнется в Тюмени. Он даст детям "
         "с синдромом Дауна возможность пройти бесплатную реабилитацию. " * 3)

ARTICLE = f"""# В Тюмени стартует программа для детей с синдромом Дауна
Общество, **18:11** 17 февраля 2026
Версия для печати
_| Фото: НКО "Центр"_
[**Далее в сюжете** _Другой проект_](https://t-l.ru/396018.html)
{_PARA}
_| Фото: НКО "Центр"_
{_PARA}
Инна Кондрашкина
Подпишитесь на наш [Telegram](https://t.me/x) и [Мах](https://max.ru/x), чтобы не пропустить
#### Поделиться:
### Ранее в [сюжете](https://t-l.ru/fabule/77)
  * 17.02.2026, 16:43[Семьи СВО познакомились](https://t-l.ru/1)
### Последние новости
  * **11:04** 19.09.2026[Боец СВО](https://t-l.ru/2)
  * **10:53** 19.09.2026[Голосование](https://t-l.ru/3)
"""


def test_clean_removes_header_footer_noise():
    out = clean_article_text(ARTICLE)
    assert out.startswith("# В Тюмени стартует")
    assert "Реализация масштабного" in out
    for junk in ("Версия для печати", "Далее в сюжете", "Фото:", "Подпишитесь",
                 "Последние новости", "Боец СВО", "https://", "Ранее в"):
        assert junk not in out, junk


def test_clean_keeps_link_text():
    text = ("# Т\n" + "Абзац про [Институт уникальных детей](https://x.ru/a) и их работу. " * 8)
    out = clean_article_text(text)
    assert "Институт уникальных детей" in out and "https://" not in out


def test_clean_link_block_without_marker_is_cut():
    links = "\n".join(f"  * [Новость {i}](https://s.ru/{i})" for i in range(4))
    out = clean_article_text(f"# Т\n{_PARA}\n{links}\n")
    assert "Новость" not in out and "Реализация" in out


def test_clean_short_result_falls_back_to_original():
    text = "Короткий текст новости без мусора."
    assert clean_article_text(text) == text


def test_clean_truncates_at_limit():
    text = "# Т\n" + "\n".join(f"Строка номер {i} " + "слово " * 20 for i in range(200))
    assert len(clean_article_text(text)) <= MAX_CHARS


def test_call_ollama_passes_num_ctx(monkeypatch):
    seen = {}

    class Resp:
        def raise_for_status(self): ...
        def json(self): return {"message": {"content": '{"title": "A"}'}}

    def fake_post(url, json=None, timeout=None, **kw):
        seen["json"], seen["url"] = json, url
        return Resp()

    monkeypatch.setattr(httpx, "post", fake_post)
    cfg = LlmConfig(provider="ollama", model="m", endpoint="http://h:11434/api/chat",
                    temperature=0.1, max_tokens=800, prompt_template="{source_text}", num_ctx=8192)
    assert _call_ollama("p", cfg) == '{"title": "A"}'
    assert seen["json"]["options"]["num_ctx"] == 8192
    assert seen["json"]["stream"] is False


def test_load_config_env_override(monkeypatch):
    monkeypatch.setenv("NEWS_LLM_ENDPOINT", "http://host.docker.internal:11434/api/chat")
    monkeypatch.setenv("NEWS_LLM_MODEL", "other:7b")
    cfg = load_llm_config()
    assert cfg.endpoint == "http://host.docker.internal:11434/api/chat"
    assert cfg.model == "other:7b" and cfg.provider == "ollama" and cfg.num_ctx == 8192


def test_add_single_url_llm_unavailable(tmp_path, monkeypatch):
    md = tmp_path / "a.md"
    md.write_text("# T\n" + _PARA, encoding="utf-8")

    async def fake_download(source, data_root=None):
        return {"content_path": str(md), "source_url": source["url"], "title": "T"}

    def boom(source, config=None):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(collect, "download_single", fake_download)
    monkeypatch.setattr(collect, "generate_draft", boom)
    res = asyncio.run(collect.add_single_url("https://d.org/n/1", db_path=tmp_path / "n.db"))
    assert res == "llm_unavailable"

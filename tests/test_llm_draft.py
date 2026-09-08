"""Тесты src/news/llm_draft.py (issue #46)."""
import json

import pytest

from src.news.llm_draft import (
    LlmConfig,
    build_prompt,
    parse_llm_json,
    generate_draft,
    call_llm,
)


def _cfg(**overrides) -> LlmConfig:
    base = dict(
        provider="anthropic",
        model="claude-sonnet-4-6",
        endpoint="https://api.anthropic.com/v1/messages",
        temperature=0.3,
        max_tokens=1500,
        prompt_template="{source_name}|{source_url}|{source_title}|{source_text}",
    )
    base.update(overrides)
    return LlmConfig(**base)


def test_build_prompt_fills_placeholders():
    prompt = build_prompt(
        _cfg(),
        {"source_name": "N", "source_url": "U", "title": "T", "text": "X"},
    )
    assert prompt == "N|U|T|X"


def test_parse_llm_json_plain():
    assert parse_llm_json('{"title": "A"}') == {"title": "A"}


def test_parse_llm_json_strips_markdown_fence():
    raw = "```json\n{\"title\": \"A\"}\n```"
    assert parse_llm_json(raw) == {"title": "A"}


def test_parse_llm_json_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_llm_json("not json")


def test_call_llm_unknown_provider_raises():
    with pytest.raises(ValueError):
        call_llm("prompt", _cfg(provider="bogus"))


def test_generate_draft_builds_item(monkeypatch):
    monkeypatch.setattr(
        "src.news.llm_draft.call_llm",
        lambda prompt, config: json.dumps(
            {"title": "Заголовок", "summary": "Кратко", "body_md": "Текст", "tags": ["сд"]}
        ),
    )
    source = {
        "source_url": "https://example.com/news/1",
        "source_name": "Example",
        "title": "Src title",
        "text": "Src text",
    }
    item = generate_draft(source, _cfg())
    assert item["source_url"] == "https://example.com/news/1"
    assert item["title"] == "Заголовок"
    assert item["tags"] == ["сд"]
    assert item["status"] == "draft"
    assert item["requires_review"] is True
    assert item["channels"] == []

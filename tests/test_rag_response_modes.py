import pytest

from src.rag.response_modes import build_system_prompt, prepare_generation_request


def test_full_mode_requests_detailed_synthesis():
    prompt = build_system_prompt("full")

    assert "подробный" in prompt
    assert "синтезируя" in prompt


def test_summary_mode_requests_concise_bullets():
    prompt = build_system_prompt("summary")

    assert "краткий" in prompt
    assert "маркированным списком" in prompt


def test_response_mode_does_not_change_retrieved_chunks():
    chunks = [{"id": "a", "text": "Источник"}]

    full = prepare_generation_request("Вопрос", chunks, "full")
    summary = prepare_generation_request("Вопрос", chunks, "summary")

    assert full.chunks is chunks
    assert summary.chunks is chunks
    assert full.system_prompt != summary.system_prompt


def test_prompt_requires_inline_citations_from_chunk_urls():
    prompt = build_system_prompt("full")

    assert "инлайн-ссылку" in prompt
    assert "source_url" in prompt
    assert "Не выдумывай URL" in prompt
    assert "сразу после утверждения" in prompt


def test_unknown_response_mode_is_rejected():
    with pytest.raises(ValueError, match="response_mode"):
        build_system_prompt("brief")  # type: ignore[arg-type]

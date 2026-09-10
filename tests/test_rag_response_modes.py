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


def test_prompt_requires_explicit_coverage_gap_statement():
    prompt = build_system_prompt("full")

    assert "мои источники не содержат ответа" in prompt
    assert "Не дополняй этот аспект общими знаниями" in prompt


def test_prompt_requests_profile_aware_follow_up_questions():
    prompt = build_system_prompt("full", {"age": 3, "lifecycle_stage": "early_development"})

    assert "ровно 2–3 коротких вопроса-продолжения" in prompt
    assert "релевантных ответу и контексту пациента" in prompt
    assert "не повторять исходный вопрос" in prompt


def test_unknown_response_mode_is_rejected():
    with pytest.raises(ValueError, match="response_mode"):
        build_system_prompt("brief")  # type: ignore[arg-type]


def test_parent_audience_adds_simple_language_instruction():
    prompt = build_system_prompt("full", audience="parent")

    assert "простым языком" in prompt
    assert "без пояснения" in prompt


def test_specialist_audience_adds_terminology_instruction():
    prompt = build_system_prompt("full", audience="specialist")

    assert "профессиональную медицинскую терминологию" in prompt
    assert "клинические рекомендации" in prompt


def test_audience_is_independent_from_response_mode():
    full_parent = build_system_prompt("full", audience="parent")
    summary_parent = build_system_prompt("summary", audience="parent")

    assert "простым языком" in full_parent
    assert "простым языком" in summary_parent
    assert full_parent != summary_parent


def test_unknown_audience_is_rejected():
    with pytest.raises(ValueError, match="audience"):
        build_system_prompt("full", audience="child")  # type: ignore[arg-type]


def test_audience_is_stored_in_generation_request():
    request = prepare_generation_request("Вопрос", [], audience="parent")

    assert request.audience == "parent"
    assert "простым языком" in request.system_prompt

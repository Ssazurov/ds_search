import pytest

from src.rag.export import (
    DialogueTurn,
    PdfExportError,
    export_answer,
    export_dialogue,
    markdown_to_text,
    normalize_export_format,
    render_answer_markdown,
    render_dialogue_text,
)
from src.rag.glossary_highlight import highlight_glossary_terms


def test_glossary_highlighter_links_matches_and_protects_markdown():
    answer = "Гипотония и гипотония. `гипотония` [гипотония](https://example.test).\n```\nгипотония\n```"

    highlighted = highlight_glossary_terms(
        answer, [{"id": "term/1", "term": "гипотония"}]
    )

    assert highlighted.startswith(
        "[Гипотония](/glossary/term%2F1) и [гипотония](/glossary/term%2F1)."
    )
    assert "`гипотония`" in highlighted
    assert "[гипотония](https://example.test)" in highlighted
    assert "```\nгипотония\n```" in highlighted


def test_answer_export_can_highlight_glossary_terms():
    markdown = render_answer_markdown(
        "Термин важен.", glossary_terms=[{"id": "1", "term": "термин"}]
    )

    assert "[Термин](/glossary/1)" in markdown


def test_answer_markdown_keeps_answer_and_deduplicates_chunk_sources():
    answer = "Факт подтверждён [источником](https://example.test/source)."
    markdown = render_answer_markdown(
        answer,
        question="Что известно?",
        sources=[
            {"source_url": "https://example.test/source", "title": "Статья"},
            {"source_url": "https://example.test/source", "title": "Дубликат"},
            {"text": "chunk without attribution"},
        ],
    )

    assert "## Вопрос" in markdown
    assert answer in markdown
    assert markdown.count("https://example.test/source") == 2
    assert "Дубликат" not in markdown
    assert "chunk without attribution" not in markdown


def test_dialogue_export_includes_questions_answers_and_sources():
    dialogue = [
        DialogueTurn(
            question="Первый вопрос",
            answer="Первый ответ",
            sources=(
                {"source_url": "https://example.test/one", "title": "Первый источник"},
            ),
        ),
        {
            "user": "Второй вопрос",
            "assistant": "Второй ответ",
            "chunks": [{"source_url": "https://example.test/two"}],
        },
    ]

    text = render_dialogue_text(dialogue)

    assert "Первый вопрос" in text
    assert "Первый ответ" in text
    assert "Первый источник (https://example.test/one)" in text
    assert "Второй вопрос" in text
    assert "Второй ответ" in text
    assert "https://example.test/two" in text


def test_export_formats_return_downloadable_artifacts():
    markdown = export_answer("Ответ", "md")
    text = export_dialogue([], "text")

    assert markdown.format == "markdown"
    assert markdown.extension == ".md"
    assert isinstance(markdown.content, str)
    assert text.format == "text"
    assert text.extension == ".txt"
    assert isinstance(text.content, str)


def test_invalid_format_is_rejected():
    with pytest.raises(ValueError, match="format"):
        normalize_export_format("html")


def test_markdown_to_text_keeps_urls_from_inline_citations():
    assert markdown_to_text("[Источник](https://example.test)\n") == (
        "Источник (https://example.test)\n"
    )


def test_pdf_export_has_clear_dependency_error_when_reportlab_is_unavailable():
    reportlab = pytest.importorskip("reportlab")
    artifact = export_answer("Ответ на русском", "pdf")

    assert reportlab is not None
    assert artifact.media_type == "application/pdf"
    assert isinstance(artifact.content, bytes)
    assert artifact.content.startswith(b"%PDF")


def test_pdf_export_error_is_public_exception():
    assert issubclass(PdfExportError, RuntimeError)

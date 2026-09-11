"""Render RAG answers and dialogue history for user-facing export (issue #40).

The module deliberately accepts already generated answers and retrieved source
metadata.  It does not call retrieval or generation, so exporting a response
cannot change the RAG result.
"""
from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from xml.sax.saxutils import escape as escape_xml

from .glossary_highlight import highlight_glossary_terms


ExportFormat = Literal["pdf", "markdown", "text"]
_FORMAT_ALIASES: dict[str, ExportFormat] = {
    "pdf": "pdf",
    "markdown": "markdown",
    "md": "markdown",
    "text": "text",
    "txt": "text",
    "plain": "text",
}


class PdfExportError(RuntimeError):
    """Raised when PDF export cannot be provided by the installed tooling."""


@dataclass(frozen=True)
class SourceReference:
    """A source shown in an export.

    ``url`` is required because an export must not turn a chunk without a
    source URL into an apparently attributable reference.
    """

    url: str
    title: str = ""


@dataclass(frozen=True)
class DialogueTurn:
    """One user question, assistant answer, and its retrieved sources."""

    question: str
    answer: str
    sources: tuple[SourceReference | Mapping[str, Any] | str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _as_text(self.question))
        object.__setattr__(self, "answer", _as_text(self.answer))
        object.__setattr__(self, "sources", tuple(normalize_sources(self.sources)))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DialogueTurn":
        """Build a turn from the common chat/history dictionary shape."""
        question = value.get("question", value.get("user", value.get("prompt", "")))
        answer = value.get("answer", value.get("assistant", value.get("response", "")))
        sources = value.get("sources")
        if sources is None:
            sources = value.get("chunks", value.get("retrieved_chunks", ()))
        return cls(
            question=_as_text(question),
            answer=_as_text(answer),
            sources=tuple(normalize_sources(sources)),
        )


@dataclass(frozen=True)
class ExportArtifact:
    """Serialized export payload suitable for a download or clipboard action."""

    content: str | bytes
    format: ExportFormat
    media_type: str
    extension: str

    @property
    def is_binary(self) -> bool:
        return isinstance(self.content, bytes)


def normalize_export_format(value: str) -> ExportFormat:
    """Validate a public format value and normalize common UI aliases."""
    try:
        return _FORMAT_ALIASES[value.strip().lower()]
    except (AttributeError, KeyError) as exc:
        raise ValueError("format должен быть одним из: pdf, markdown, text") from exc


def normalize_sources(
    sources: Sequence[SourceReference | Mapping[str, Any] | str] | None,
) -> list[SourceReference]:
    """Normalize source chunks, drop unusable entries, and deduplicate URLs.

    RAG chunks commonly carry ``source_url`` and ``title`` directly.  The
    nested ``metadata`` fallback keeps the exporter compatible with chunk
    adapters that keep those fields under metadata.
    """
    if sources is None:
        return []

    result: list[SourceReference] = []
    seen_urls: set[str] = set()
    for item in sources:
        if isinstance(item, SourceReference):
            url = item.url.strip()
            title = item.title.strip()
        elif isinstance(item, str):
            url = item.strip()
            title = ""
        elif isinstance(item, Mapping):
            metadata = item.get("metadata")
            nested = metadata if isinstance(metadata, Mapping) else {}
            url = _as_text(
                item.get("source_url") or item.get("url") or nested.get("source_url")
            ).strip()
            title = _as_text(
                item.get("title")
                or item.get("source_title")
                or item.get("name")
                or nested.get("title")
                or nested.get("source_title")
            ).strip()
        else:
            continue

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        result.append(SourceReference(url=url, title=title))
    return result


def coerce_dialogue_turn(value: DialogueTurn | Mapping[str, Any]) -> DialogueTurn:
    """Accept a typed turn or a history dictionary at the public boundary."""
    if isinstance(value, DialogueTurn):
        return value
    if isinstance(value, Mapping):
        return DialogueTurn.from_mapping(value)
    raise TypeError("элемент dialogue должен быть DialogueTurn или mapping")


def render_answer_markdown(
    answer: str,
    *,
    question: str | None = None,
    sources: Sequence[SourceReference | Mapping[str, Any] | str] | None = None,
    glossary_terms: Sequence[Mapping[str, object]] | None = None,
    glossary_path: str = "/glossary",
    title: str = "Ответ",
) -> str:
    """Render one assistant answer as Markdown, including source references."""
    lines = [f"# {title.strip() or 'Ответ'}", ""]
    if question and question.strip():
        lines.extend(["## Вопрос", "", question.strip(), ""])
    answer_text = highlight_glossary_terms(
        answer.strip(), glossary_terms or (), glossary_path=glossary_path
    )
    lines.extend(["## Ответ", "", answer_text, ""])
    _append_sources_markdown(lines, normalize_sources(sources))
    return "\n".join(lines).rstrip() + "\n"


def render_dialogue_markdown(
    turns: Sequence[DialogueTurn | Mapping[str, Any]],
    *,
    title: str = "Диалог",
) -> str:
    """Render a complete question/answer history as Markdown."""
    lines = [f"# {title.strip() or 'Диалог'}", ""]
    for index, raw_turn in enumerate(turns, start=1):
        turn = coerce_dialogue_turn(raw_turn)
        lines.extend([f"## Сообщение {index}", ""])
        if turn.question.strip():
            lines.extend(["### Вопрос", "", turn.question.strip(), ""])
        lines.extend(["### Ответ", "", turn.answer.strip(), ""])
        _append_sources_markdown(lines, turn.sources)
    return "\n".join(lines).rstrip() + "\n"


def render_answer_text(
    answer: str,
    *,
    question: str | None = None,
    sources: Sequence[SourceReference | Mapping[str, Any] | str] | None = None,
    title: str = "Ответ",
) -> str:
    """Render one answer as plain text suitable for clipboard copying."""
    return markdown_to_text(
        render_answer_markdown(answer, question=question, sources=sources, title=title)
    )


def render_dialogue_text(
    turns: Sequence[DialogueTurn | Mapping[str, Any]],
    *,
    title: str = "Диалог",
) -> str:
    """Render a complete dialogue as plain text suitable for clipboard copying."""
    return markdown_to_text(render_dialogue_markdown(turns, title=title))


def markdown_to_text(markdown: str) -> str:
    """Convert the small Markdown subset used by the export template to text."""
    text = re.sub(r"```(?:[^\n]*)\n?", "", markdown)
    text = text.replace("```", "")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "- ", text, flags=re.MULTILINE)
    text = html.unescape(text)
    return text.strip() + "\n"


def export_answer(
    answer: str,
    export_format: str,
    *,
    question: str | None = None,
    sources: Sequence[SourceReference | Mapping[str, Any] | str] | None = None,
    title: str = "Ответ",
) -> ExportArtifact:
    """Serialize one answer in Markdown, plain text, or PDF format."""
    markdown = render_answer_markdown(
        answer, question=question, sources=sources, title=title
    )
    return _build_artifact(markdown, export_format)


def export_dialogue(
    turns: Sequence[DialogueTurn | Mapping[str, Any]],
    export_format: str,
    *,
    title: str = "Диалог",
) -> ExportArtifact:
    """Serialize an entire dialogue history in the selected format."""
    markdown = render_dialogue_markdown(turns, title=title)
    return _build_artifact(markdown, export_format)


# ``response`` is the term used by the RAG API, while ``answer`` is the term
# used in the UI.  Keep both names available without duplicating behavior.
export_response = export_answer


def _build_artifact(markdown: str, export_format: str) -> ExportArtifact:
    normalized = normalize_export_format(export_format)
    if normalized == "markdown":
        return ExportArtifact(markdown, normalized, "text/markdown; charset=utf-8", ".md")
    if normalized == "text":
        return ExportArtifact(
            markdown_to_text(markdown), normalized, "text/plain; charset=utf-8", ".txt"
        )
    return ExportArtifact(
        _render_pdf(markdown_to_text(markdown)), normalized, "application/pdf", ".pdf"
    )


def _append_sources_markdown(lines: list[str], sources: Sequence[SourceReference]) -> None:
    if not sources:
        return
    lines.extend(["### Источники", ""])
    for source in sources:
        label = _escape_markdown_label(source.title.strip() or source.url)
        lines.append(f"- [{label}]({source.url})")
    lines.append("")


def _escape_markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def _render_pdf(text: str) -> bytes:
    """Render text through ReportLab, the project's PDF export dependency."""
    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise PdfExportError(
            "PDF export requires reportlab; install dependencies from requirements.txt"
        ) from exc

    font_name = _register_unicode_font(pdfmetrics, TTFont)
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "DsExportBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
        wordWrap="CJK",
    )
    heading = ParagraphStyle(
        "DsExportHeading",
        parent=body,
        fontSize=15,
        leading=19,
        spaceBefore=2 * mm,
        spaceAfter=4 * mm,
    )

    story = []
    for line in text.splitlines():
        if not line.strip():
            story.append(Spacer(1, 3 * mm))
            continue
        content = escape_xml(line)
        if line.startswith("Источники") or line in {"Ответ", "Диалог", "Вопрос"}:
            story.append(Paragraph(content, heading))
        else:
            story.append(Paragraph(content, body))

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="ds_search export",
    )
    document.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    return output.getvalue()


def _register_unicode_font(pdfmetrics: Any, ttf_type: Any) -> str:
    font_name = "DsSearchExportFont"
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name

    candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/mnt/c/Windows/Fonts/arial.ttf"),
        Path("/mnt/c/Windows/Fonts/segoeui.ttf"),
    )
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(ttf_type(font_name, str(path)))
            return font_name
    raise PdfExportError("PDF export requires a Unicode TrueType font")


def _draw_page_number(canvas: Any, document: Any) -> None:
    from reportlab.lib.units import mm

    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(
        document.pagesize[0] - 20 * mm, 10 * mm, str(canvas.getPageNumber())
    )
    canvas.restoreState()

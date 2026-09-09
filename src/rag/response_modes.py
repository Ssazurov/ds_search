"""Generation prompt modes for the RAG chat contract (issue #34, ADR-0002)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


ResponseMode = Literal["full", "summary"]

_MODE_INSTRUCTIONS: dict[ResponseMode, str] = {
    "full": (
        "Дай связный подробный ответ, синтезируя только переданные фрагменты "
        "источников."
    ),
    "summary": (
        "Дай краткий ответ маркированным списком, используя только переданные "
        "фрагменты источников."
    ),
}


@dataclass(frozen=True)
class GenerationRequest:
    """Generation input; ``chunks`` is exactly the retrieval result."""

    question: str
    chunks: Sequence[dict]
    system_prompt: str
    response_mode: ResponseMode


def build_system_prompt(response_mode: ResponseMode) -> str:
    """Return generation instructions for one validated response mode."""
    try:
        instruction = _MODE_INSTRUCTIONS[response_mode]
    except KeyError as exc:
        raise ValueError("response_mode должен быть 'full' или 'summary'") from exc

    return (
        "Ты RAG-ассистент по синдрому Дауна. "
        f"{instruction} "
        "Не добавляй сведения вне этих фрагментов."
    )


def prepare_generation_request(
    question: str,
    retrieved_chunks: Sequence[dict],
    response_mode: ResponseMode = "full",
) -> GenerationRequest:
    """Bind a response mode after retrieval without altering retrieved chunks."""
    return GenerationRequest(
        question=question,
        chunks=retrieved_chunks,
        system_prompt=build_system_prompt(response_mode),
        response_mode=response_mode,
    )

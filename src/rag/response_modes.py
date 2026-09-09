"""Generation prompt modes for the RAG chat contract (issue #34, ADR-0002)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from .patient_profile import PatientProfile, validate_patient_profile


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
    patient_profile: PatientProfile | None = None


def build_system_prompt(
    response_mode: ResponseMode,
    patient_profile: Mapping[str, Any] | None = None,
) -> str:
    """Return generation instructions for one validated response mode."""
    try:
        instruction = _MODE_INSTRUCTIONS[response_mode]
    except KeyError as exc:
        raise ValueError("response_mode должен быть 'full' или 'summary'") from exc

    profile = validate_patient_profile(patient_profile)
    profile_context = f" Контекст пациента: {profile}." if profile else ""
    return (
        "Ты RAG-ассистент по синдрому Дауна. "
        f"{instruction} "
        "Не добавляй сведения вне этих фрагментов."
        f"{profile_context}"
    )


def prepare_generation_request(
    question: str,
    retrieved_chunks: Sequence[dict],
    response_mode: ResponseMode = "full",
    patient_profile: Mapping[str, Any] | None = None,
) -> GenerationRequest:
    """Bind a response mode after retrieval without altering retrieved chunks."""
    return GenerationRequest(
        question=question,
        chunks=retrieved_chunks,
        system_prompt=build_system_prompt(response_mode, patient_profile),
        response_mode=response_mode,
        patient_profile=validate_patient_profile(patient_profile),
    )

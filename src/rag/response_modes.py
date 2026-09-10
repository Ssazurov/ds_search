"""Generation prompt modes for the RAG chat contract (issue #34, ADR-0002)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from .patient_profile import PatientProfile, validate_patient_profile


ResponseMode = Literal["full", "summary"]
Audience = Literal["parent", "specialist"]

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

_AUDIENCE_INSTRUCTIONS: dict[Audience, str] = {
    "parent": (
        "Объясняй простым языком, избегай сложной медицинской терминологии "
        "без пояснения."
    ),
    "specialist": (
        "Используй профессиональную медицинскую терминологию, ссылайся на "
        "клинические рекомендации где возможно."
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
    audience: Audience | None = None


def build_system_prompt(
    response_mode: ResponseMode,
    patient_profile: Mapping[str, Any] | None = None,
    audience: Audience | None = None,
) -> str:
    """Return generation instructions for one validated response mode."""
    try:
        instruction = _MODE_INSTRUCTIONS[response_mode]
    except KeyError as exc:
        raise ValueError("response_mode должен быть 'full' или 'summary'") from exc

    if audience is not None:
        try:
            audience_instruction = _AUDIENCE_INSTRUCTIONS[audience]
        except KeyError as exc:
            raise ValueError("audience должен быть 'parent' или 'specialist'") from exc
    else:
        audience_instruction = ""

    profile = validate_patient_profile(patient_profile)
    profile_context = f" Контекст пациента: {profile}." if profile else ""
    return (
        "Ты RAG-ассистент по синдрому Дауна. "
        f"{instruction} "
        f"{audience_instruction} "
        "Не добавляй сведения вне этих фрагментов. "
        "Для каждого проверяемого утверждения ставь инлайн-ссылку на источник "
        "сразу после утверждения в формате [источник](source_url) или "
        "[источник N](source_url), используя только source_url из переданных "
        "фрагментов. Не выдумывай URL и не выноси источники только в отдельный "
        "список в конце ответа. Если переданные фрагменты не покрывают какой-либо "
        "аспект вопроса, явно скажи: «мои источники не содержат ответа». Не "
        "дополняй этот аспект общими знаниями и не выдавай молчаливое умолчание "
        "за ответ. Если отдельное утверждение нельзя связать с источником, не "
        "включай его в ответ. После основного ответа предложи отдельным списком "
        "ровно 2–3 коротких вопроса-продолжения, релевантных ответу и контексту "
        "пациента. Вопросы должны помогать выбрать следующий шаг, не содержать "
        "неподтверждённых фактов и не повторять исходный вопрос."
        f"{profile_context}"
    )


def prepare_generation_request(
    question: str,
    retrieved_chunks: Sequence[dict],
    response_mode: ResponseMode = "full",
    patient_profile: Mapping[str, Any] | None = None,
    audience: Audience | None = None,
) -> GenerationRequest:
    """Bind a response mode after retrieval without altering retrieved chunks."""
    return GenerationRequest(
        question=question,
        chunks=retrieved_chunks,
        system_prompt=build_system_prompt(response_mode, patient_profile, audience),
        response_mode=response_mode,
        patient_profile=validate_patient_profile(patient_profile),
        audience=audience,
    )

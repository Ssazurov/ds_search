"""Patient profile validation and metadata filtering for RAG chat (issue #36)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class PatientProfile(TypedDict, total=False):
    age: str | int | float
    sex: str
    diagnosis: str
    comorbidities: list[str]
    lifecycle_stage: str


_PROFILE_FIELDS = {"age", "sex", "diagnosis", "comorbidities", "lifecycle_stage"}


def validate_patient_profile(profile: Mapping[str, Any] | None) -> PatientProfile | None:
    """Validate the public profile shape without inferring missing values."""
    if profile is None:
        return None
    unknown = set(profile) - _PROFILE_FIELDS
    if unknown:
        raise ValueError(f"неизвестные поля patient_profile: {sorted(unknown)}")
    if "comorbidities" in profile:
        tags = profile["comorbidities"]
        if not isinstance(tags, Sequence) or isinstance(tags, (str, bytes)):
            raise ValueError("patient_profile.comorbidities должен быть списком")
        if not all(isinstance(tag, str) and tag.strip() for tag in tags):
            raise ValueError("patient_profile.comorbidities должен содержать непустые строки")
    return dict(profile)  # type: ignore[return-value]


def filter_chunks_by_patient_profile(
    chunks: Sequence[dict], profile: Mapping[str, Any] | None
) -> list[dict]:
    """Keep chunks matching profile retrieval metadata.

    Only ``lifecycle_stage`` and ``comorbidity_tags`` are retrieval filters;
    demographic fields remain generation context. Chunks without the requested
    metadata are not treated as matching.
    """
    validated = validate_patient_profile(profile)
    if not validated:
        return list(chunks)
    stage = validated.get("lifecycle_stage")
    requested_tags = {tag.strip().casefold() for tag in validated.get("comorbidities", [])}
    if not stage and not requested_tags:
        return list(chunks)

    result = []
    for chunk in chunks:
        metadata = chunk.get("metadata", chunk)
        if stage and metadata.get("lifecycle_stage") != stage:
            continue
        chunk_tags = metadata.get("comorbidity_tags", [])
        if requested_tags and not requested_tags.intersection(
            {str(tag).strip().casefold() for tag in chunk_tags}
        ):
            continue
        result.append(chunk)
    return result

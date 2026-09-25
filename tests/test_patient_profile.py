import pytest

from src.rag.patient_profile import filter_chunks_by_patient_profile, validate_patient_profile
from src.rag.response_modes import prepare_generation_request


def test_profile_is_included_in_generation_context():
    profile = {"age": 4, "sex": "female"}
    request = prepare_generation_request("Вопрос", [], patient_profile=profile)

    assert request.patient_profile == profile
    assert "Контекст пациента" in request.system_prompt


def test_profile_filters_comorbidity_metadata():
    chunks = [
        {"id": "match", "comorbidity_tags": ["hearing"]},
        {"id": "wrong-tag", "comorbidity_tags": ["vision"]},
    ]

    result = filter_chunks_by_patient_profile(
        chunks, {"comorbidities": ["HEARING"]}
    )

    assert [chunk["id"] for chunk in result] == ["match"]


def test_profile_without_retrieval_fields_preserves_chunks():
    chunks = [{"id": "a"}]
    assert filter_chunks_by_patient_profile(chunks, {"age": 4}) == chunks


def test_unknown_profile_field_is_rejected():
    with pytest.raises(ValueError, match="patient_profile"):
        validate_patient_profile({"unknown": "value"})

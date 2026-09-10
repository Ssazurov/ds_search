import pytest

from src.rag.sessions import SessionStore, SessionTopic


def test_session_is_bound_to_topic_and_inherits_shared_profile():
    profile = {"age": 4, "lifecycle_stage": "early_development"}
    store = SessionStore(profile)

    session = store.create({"lifecycle_stage": "early_development"})

    assert session.topic.lifecycle_stage == "early_development"
    assert session.patient_profile == profile


def test_histories_are_isolated_between_topics():
    store = SessionStore()
    first = store.create(SessionTopic(category="speech_development"))
    second = store.create(SessionTopic(category="school_preparation"))

    store.add_turn(first.session_id, "Первый вопрос", "Первый ответ")

    assert len(first.turns) == 1
    assert second.turns == []


def test_switch_creates_new_empty_session_with_inherited_profile():
    store = SessionStore({"diagnosis": "trisomy 21"})
    old = store.create(SessionTopic(lifecycle_stage="prenatal"))
    store.add_turn(old.session_id, "Вопрос", "Ответ")

    new = store.switch(old.session_id, {"lifecycle_stage": "medical"})

    assert new.session_id != old.session_id
    assert new.patient_profile == old.patient_profile
    assert new.turns == []
    assert len(old.turns) == 1


def test_invalid_lifecycle_stage_is_rejected():
    with pytest.raises(ValueError, match="lifecycle_stage"):
        SessionTopic(lifecycle_stage="unknown-stage")


def test_topic_requires_stage_or_category():
    with pytest.raises(ValueError, match="тема"):
        SessionTopic()


def test_missing_session_is_rejected():
    with pytest.raises(KeyError, match="сессия не найдена"):
        SessionStore().get("missing")

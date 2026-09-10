"""Thematic RAG sessions (notebooks) bound to lifecycle topics (issue #43)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4

from src.metadata.profile import LIFECYCLE_STAGES

from .export import SourceReference, normalize_sources
from .patient_profile import PatientProfile, validate_patient_profile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SessionTopic:
    """A session topic from the information architecture."""

    lifecycle_stage: str | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        if self.lifecycle_stage is None and self.category is None:
            raise ValueError("тема должна содержать lifecycle_stage или category")
        if self.lifecycle_stage is not None and self.lifecycle_stage not in LIFECYCLE_STAGES:
            raise ValueError(
                f"неизвестный lifecycle_stage: {self.lifecycle_stage!r}"
            )


@dataclass(frozen=True)
class SessionTurn:
    """One isolated question/answer turn in a thematic session."""

    question: str
    answer: str
    sources: tuple[SourceReference, ...] = ()
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", str(self.question))
        object.__setattr__(self, "answer", str(self.answer))
        object.__setattr__(self, "sources", tuple(normalize_sources(self.sources)))


@dataclass
class ThematicSession:
    """Notebook with a topic-local history and an inherited profile snapshot."""

    session_id: str
    topic: SessionTopic
    patient_profile: PatientProfile | None = None
    turns: list[SessionTurn] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def add_turn(
        self,
        question: str,
        answer: str,
        sources: Sequence[SourceReference | Mapping[str, Any] | str] | None = None,
    ) -> SessionTurn:
        turn = SessionTurn(question, answer, tuple(normalize_sources(sources)))
        self.turns.append(turn)
        self.updated_at = _now()
        return turn

    def inherit_profile(self, profile: Mapping[str, Any] | None) -> None:
        self.patient_profile = validate_patient_profile(profile)
        self.updated_at = _now()


class SessionStore:
    """In-memory session registry; persistence belongs to the chat host."""

    def __init__(self, shared_profile: Mapping[str, Any] | None = None) -> None:
        self._shared_profile = validate_patient_profile(shared_profile)
        self._sessions: dict[str, ThematicSession] = {}

    @property
    def shared_profile(self) -> PatientProfile | None:
        return self._shared_profile

    def set_shared_profile(self, profile: Mapping[str, Any] | None) -> None:
        self._shared_profile = validate_patient_profile(profile)

    def create(
        self,
        topic: SessionTopic | Mapping[str, Any],
        patient_profile: Mapping[str, Any] | None = None,
    ) -> ThematicSession:
        topic_value = topic if isinstance(topic, SessionTopic) else SessionTopic(**dict(topic))
        profile = self._shared_profile if patient_profile is None else validate_patient_profile(patient_profile)
        session = ThematicSession(uuid4().hex, topic_value, profile)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ThematicSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"сессия не найдена: {session_id}") from exc

    def list(self) -> list[ThematicSession]:
        return sorted(self._sessions.values(), key=lambda item: item.updated_at, reverse=True)

    def add_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        sources: Sequence[SourceReference | Mapping[str, Any] | str] | None = None,
    ) -> SessionTurn:
        return self.get(session_id).add_turn(question, answer, sources)

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def switch(self, session_id: str, topic: SessionTopic | Mapping[str, Any]) -> ThematicSession:
        """Create a fresh notebook while preserving the profile, not history."""
        previous = self.get(session_id)
        return self.create(topic, previous.patient_profile)

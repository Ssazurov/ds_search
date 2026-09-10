"""Query decomposition for complex RAG questions (issue #41, ADR-0002 п.10).

Сложный вопрос (несколько тем сразу — напр. диагноз+сопутствующее состояние+этап)
разбивается на 2-5 под-запросов перед retrieval. Для простых вопросов декомпозиция
не применяется — эвристика определяет необходимость.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DecomposedQuery:
    """Result of query decomposition."""

    original: str
    sub_queries: tuple[str, ...]
    decomposed: bool


# Conjunctions that typically separate distinct topics in Russian.
_TOPIC_CONJUNCTIONS: list[str] = [
    r"\s+и\s+",
    r"\s+или\s+",
    r"\s+а также\s+",
]

# Strong separators that almost always indicate distinct topics.
_STRONG_SEPARATORS: list[str] = [
    r"\s*;\s*",
]


def _count_topic_markers(text: str) -> int:
    """Count topic-bearing conjunctions and separators in text."""
    count = 0
    for pattern in _TOPIC_CONJUNCTIONS + _STRONG_SEPARATORS:
        count += len(re.findall(pattern, text, flags=re.IGNORECASE))
    # Each comma can separate distinct topics.
    count += text.count(",")
    return count


def _is_complex(question: str) -> bool:
    """Heuristic: question is complex if it has 2+ topic markers.

    Conservative threshold: simple questions with a single "и" (e.g.
    "диагностика и лечение") stay intact. Only clearly multi-topic questions
    are decomposed.
    """
    return _count_topic_markers(question) >= 2


def _split_question(question: str) -> list[str]:
    """Split question into sub-queries by conjunctions/separators.

    Order of splitting (strongest separator first):
    1. semicolon
    2. topic conjunctions (и, или, а также)
    3. comma (only when it creates 3+ parts, i.e. 2+ commas)
    """
    parts = [question]

    # 1) Strong separators first.
    for pattern in _STRONG_SEPARATORS:
        new_parts: list[str] = []
        for part in parts:
            splits = re.split(pattern, part)
            new_parts.extend([s.strip() for s in splits if s.strip()])
        parts = new_parts

    # 2) Topic conjunctions.
    for pattern in _TOPIC_CONJUNCTIONS:
        new_parts = []
        for part in parts:
            splits = re.split(pattern, part, flags=re.IGNORECASE)
            new_parts.extend([s.strip() for s in splits if s.strip()])
        parts = new_parts

    # 3) Comma split only when it yields 3+ parts (2+ commas).
    if len(parts) == 1 and question.count(",") >= 2:
        parts = [p.strip() for p in question.split(",") if p.strip()]

    return parts


def decompose_query(
    question: str,
    max_sub_queries: int = 5,
) -> DecomposedQuery:
    """Decompose a complex question into sub-queries for parallel retrieval.

    For simple questions, returns the original as a single sub-query with
    ``decomposed=False``. For complex questions, splits into 2-5 sub-queries
    and returns ``decomposed=True``.

    Args:
        question: User question to potentially decompose.
        max_sub_queries: Upper bound for the number of sub-queries.

    Returns:
        DecomposedQuery with the original question and the sub-queries tuple.
    """
    if not question or not question.strip():
        return DecomposedQuery(
            original=question or "",
            sub_queries=(question or "",),
            decomposed=False,
        )

    question = question.strip()

    if not _is_complex(question):
        return DecomposedQuery(
            original=question,
            sub_queries=(question,),
            decomposed=False,
        )

    sub_queries = _split_question(question)

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for q in sub_queries:
        normalized = q.lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(q)

    # Clamp to max_sub_queries.
    if len(unique) > max_sub_queries:
        unique = unique[:max_sub_queries]

    # If decomposition produced only one meaningful sub-query, keep original.
    if len(unique) <= 1:
        return DecomposedQuery(
            original=question,
            sub_queries=(question,),
            decomposed=False,
        )

    return DecomposedQuery(
        original=question,
        sub_queries=tuple(unique),
        decomposed=True,
    )

"""Keyword/BM25-эвристика для suggested_direction/category/doc_type/
target_audience в discovered_sources (issue #21, ADR-002 п.6, финал).

Дёшево, без внешних вызовов: считает вхождения RU-ключевиков из
config/classifier_keywords.yaml в title+snippet находки. Черновая
предфильтрация для UI (issue #16/#19) — пользователь может
поправить/переопределить руками; LLM-классификация — отдельная задача
после MVP (не в этом issue).

Ключи словарей сверяются с config/categories.yaml (directions/doc_types/
target_audiences) — категория без ключевиков в classifier_keywords.yaml
просто не будет предложена (suggested_* = None), это не ошибка.

dictionary_suggestions (авто-находка новых терминов) — вне скоупа: у
gar-core-api discovery API (PR #222, schemas/discovery.py) нет такой
модели/эндпоинта (см. ADR-002, открытый вопрос 6). Реализуется после
появления backend-а.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..metadata.schema import load_dictionaries

_KEYWORDS_PATH = Path(__file__).resolve().parents[2] / "config" / "classifier_keywords.yaml"

_WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


def load_keywords(path: Path = _KEYWORDS_PATH) -> dict:
    """category/doc_type/target_audience -> {метка: [ru-ключевики]}."""
    if not path.exists():
        return {"category": {}, "doc_type": {}, "target_audience": {}}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "category": data.get("category", {}),
        "doc_type": data.get("doc_type", {}),
        "target_audience": data.get("target_audience", {}),
    }


def _score_labels(text: str, label_keywords: dict[str, list[str]]) -> dict[str, int]:
    """Для каждой метки — число вхождений её ключевиков (substring-match по
    нормализованному тексту, keyword-overlap, не точный BM25 — issue #21
    сознательно называет его "BM25-эвристикой", не полной реализацией)."""
    scores: dict[str, int] = {}
    for label, keywords in label_keywords.items():
        count = sum(text.count(kw.lower()) for kw in keywords)
        if count:
            scores[label] = count
    return scores


def _best_label(scores: dict[str, int]) -> str | None:
    if not scores:
        return None
    return max(scores, key=scores.get)


def classify(
    title: str | None,
    snippet: str | None,
    categories_path: Path | None = None,
    keywords_path: Path = _KEYWORDS_PATH,
) -> dict:
    """Возвращает {"suggested_direction", "suggested_category",
    "suggested_doc_type", "suggested_target_audience"}, значения — метка
    или None (нет уверенного совпадения; ADR-002: null, не выдумываем)."""
    text = _normalize(" ".join(filter(None, [title, snippet])))
    result = {
        "suggested_direction": None,
        "suggested_category": None,
        "suggested_doc_type": None,
        "suggested_target_audience": None,
    }
    if not text:
        return result

    kw = load_keywords(keywords_path)
    dicts = load_dictionaries(categories_path) if categories_path else load_dictionaries()
    directions = dicts["directions"]  # direction -> [category, ...]

    category_scores = _score_labels(text, kw["category"])
    if category_scores:
        best_category = _best_label(category_scores)
        for direction, categories in directions.items():
            if best_category in categories:
                result["suggested_direction"] = direction
                result["suggested_category"] = best_category
                break

    doc_type_scores = _score_labels(text, kw["doc_type"])
    result["suggested_doc_type"] = _best_label(doc_type_scores)

    audience_scores = _score_labels(text, kw["target_audience"])
    result["suggested_target_audience"] = _best_label(audience_scores)

    return result

"""Доменная схема метаданных для GAR (issue #4, ADR-001 п.2).

Константы — fallback-дефолты. Реальный источник правды —
config/categories.yaml (issue #19: CRUD справочников через ui/), читается
load_dictionaries()/пишется save_dictionaries(). Не связана с
metadata_schema.yaml gar-docling-intake (та схема — под техдокументацию
product/doc_type/version). DIRECTIONS/DOC_TYPES/... оставлены для обратной
совместимости (issue #5 адаптер ds_ingestion), но актуальные значения
нужно брать из load_dictionaries().
"""
from __future__ import annotations

import copy
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

DIRECTIONS = ["methodology", "medicine", "law", "science", "news"]

DOC_TYPES = [
    "book", "guide", "article", "law", "dissertation",
    "clinical_recommendation", "brochure", "program", "systematic_review",
    "report",
]

TARGET_AUDIENCES = ["parents", "specialists", "researchers"]

AGE_GROUPS = ["prenatal", "0-3", "4-7", "8-12", "13-17", "18+"]

# Фиксированный enum backend'а (gar-core-api PR #222, LICENSE_STATUSES) —
# не редактируется через справочники, любое другое значение backend
# отклонит 422.
LICENSE_STATUSES = ["unknown", "allow", "attribution_required", "deny", "pending_manual_review", "own_generated"]

# Обязательные поля документа при загрузке в GAR (ADR-001 п.2).
REQUIRED_FIELDS = ["source_url", "source_domain", "title", "license", "direction"]

_CATEGORIES_PATH = Path(__file__).resolve().parents[2] / "config" / "categories.yaml"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_DEFAULT_DICTIONARIES = {
    "directions": {d: [] for d in DIRECTIONS},
    "doc_types": list(DOC_TYPES),
    "target_audiences": list(TARGET_AUDIENCES),
    "age_groups": list(AGE_GROUPS),
    "license_statuses": list(LICENSE_STATUSES),
}


def load_categories(path: Path = _CATEGORIES_PATH) -> dict[str, list[str]]:
    """direction -> список category (обратная совместимость с issue #4/#5)."""
    return load_dictionaries(path)["directions"]


def load_dictionaries(path: Path = _CATEGORIES_PATH) -> dict:
    """Все справочники из categories.yaml (issue #19 п.1). Отсутствующие
    ключи/файл — заполняются дефолтами, чтобы UI не падал на пустом репо."""
    data: dict = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("categories.yaml root must be a map")
        if "directions" not in data and data and all(isinstance(v, list) for v in data.values()):
            # legacy-формат (до issue #19): весь файл = direction -> category
            data = {"directions": data}
    result = {}
    for key, default in _DEFAULT_DICTIONARIES.items():
        result[key] = data.get(key, default)
    return result


def validate_dictionaries(dictionaries: dict[str, Any]) -> None:
    """Validate the editable dictionary structure before it is persisted."""
    if not isinstance(dictionaries, dict):
        raise ValueError("Справочники должны быть YAML-объектом")
    directions = dictionaries.get("directions")
    if not isinstance(directions, dict):
        raise ValueError("Секция directions должна быть объектом")
    seen_directions: set[str] = set()
    for direction, categories in directions.items():
        _validate_identifier(direction, "направление")
        if direction in seen_directions:
            raise ValueError(f"Дубликат направления: {direction}")
        seen_directions.add(direction)
        if not isinstance(categories, list):
            raise ValueError(f"Категории направления {direction} должны быть массивом")
        seen_categories: set[str] = set()
        for category in categories:
            _validate_identifier(category, "категория")
            if category in seen_categories:
                raise ValueError(f"Дубликат категории в направлении {direction}: {category}")
            seen_categories.add(category)


def _validate_identifier(value: Any, kind: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Имя {kind} не может быть пустым")
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"Некорректный идентификатор {kind}: используйте латинские буквы, цифры и _"
        )


def save_dictionaries(dictionaries: dict, path: Path = _CATEGORIES_PATH) -> None:
    """Atomically validate and save dictionaries without dropping YAML sections."""
    candidate = copy.deepcopy(dictionaries)
    validate_dictionaries(candidate)
    original: dict[str, Any] = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            original = yaml.safe_load(f) or {}
        if not isinstance(original, dict):
            raise ValueError("categories.yaml root must be a map")
    if "license_statuses" in original and candidate.get("license_statuses") != original["license_statuses"]:
        raise ValueError("license_statuses нельзя изменять через UI")
    original["directions"] = candidate["directions"]
    for key in ("doc_types", "target_audiences", "age_groups", "license_statuses"):
        if key in candidate:
            original[key] = candidate[key]
    validate_dictionaries(original)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as f:
            temporary = f.name
            yaml.safe_dump(original, f, allow_unicode=True, sort_keys=False)
        with open(temporary, encoding="utf-8") as f:
            written = yaml.safe_load(f)
        if not isinstance(written, dict):
            raise ValueError("Сохранённый YAML должен быть объектом")
        validate_dictionaries(written)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

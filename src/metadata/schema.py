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

from pathlib import Path

import yaml

DIRECTIONS = ["methodology", "medicine", "law", "science"]

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
LICENSE_STATUSES = ["unknown", "allow", "attribution_required", "deny", "pending_manual_review"]

# Обязательные поля документа при загрузке в GAR (ADR-001 п.2).
REQUIRED_FIELDS = ["source_url", "source_domain", "title", "license", "direction"]

_CATEGORIES_PATH = Path(__file__).resolve().parents[2] / "config" / "categories.yaml"

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
        if "directions" not in data and data and all(isinstance(v, list) for v in data.values()):
            # legacy-формат (до issue #19): весь файл = direction -> category
            data = {"directions": data}
    result = {}
    for key, default in _DEFAULT_DICTIONARIES.items():
        result[key] = data.get(key, default)
    return result


def save_dictionaries(dictionaries: dict, path: Path = _CATEGORIES_PATH) -> None:
    """Пишет справочники обратно в categories.yaml (issue #19 п.1)."""
    ordered = {k: dictionaries.get(k, v) for k, v in _DEFAULT_DICTIONARIES.items()}
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(ordered, f, allow_unicode=True, sort_keys=False)

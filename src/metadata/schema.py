"""Доменная схема метаданных для GAR (issue #4, ADR-001 п.2).

Константы + загрузчик config/categories.yaml. Не связана с
metadata_schema.yaml gar-docling-intake (та схема — под техдокументацию
product/doc_type/version). Используется адаптером ds_ingestion (issue #5)
для регистрации per-dataset metadata dictionary через
POST /datasets/{id}/metadata-fields в gar-core-api.
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

LICENSE_STATUSES = [
    "allow", "attribution_required", "deny", "pending_manual_review",
]

# Обязательные поля документа при загрузке в GAR (ADR-001 п.2).
REQUIRED_FIELDS = ["source_url", "source_domain", "title", "license", "direction"]

_CATEGORIES_PATH = Path(__file__).resolve().parents[2] / "config" / "categories.yaml"


def load_categories(path: Path = _CATEGORIES_PATH) -> dict[str, list[str]]:
    """direction -> список category (config/categories.yaml)."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

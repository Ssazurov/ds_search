"""Fallback-дефолты metadata-полей на уровне источника (issue #90, эпик #88).

Используется, когда LLM-классификатор (issue #91) недоступен/дал ошибку.
config/gar_mapping.yaml хранит дефолты per-source (domain[/dest_dir]);
resolve_defaults() сливает общий и специфичный уровни, более специфичный
переопределяет общий."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_MAPPING_PATH = Path(__file__).resolve().parents[2] / "config" / "gar_mapping.yaml"


def load_mapping(path: Path = _MAPPING_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("sources", {})


def resolve_defaults(
    domain: str,
    dest_dir: str | None = None,
    mapping: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Дефолты для источника: domain-уровень + domain/dest_dir поверх него.
    Отсутствие записи для домена — пустой словарь (не ошибка), выше по
    пайплайну это просто означает "дефолтов нет, полагаемся на LLM/needs_review".
    """
    mapping = mapping if mapping is not None else load_mapping()
    result: dict[str, str] = dict(mapping.get(domain, {}))
    if dest_dir:
        specific = mapping.get(f"{domain}/{dest_dir}")
        if specific:
            result.update(specific)
    return result


def validate_mapping(
    mapping: dict[str, dict[str, Any]],
    gar_fields: dict,
) -> list[str]:
    """Список ошибок: значения из mapping, которых нет среди активных опций
    в актуальной схеме GAR (gar_schema.py). Пустой список — всё валидно."""
    from . import gar_schema

    errors: list[str] = []
    for source_key, defaults in mapping.items():
        direction_value = defaults.get("direction")
        for field_key, value in defaults.items():
            if field_key == "category":
                valid = (
                    gar_schema.category_options_for_direction(gar_fields, direction_value)
                    if direction_value else []
                )
            else:
                valid = gar_schema.field_options(gar_fields, field_key)
            if valid and value not in valid:
                errors.append(
                    f"{source_key}: {field_key}={value!r} не входит в допустимые {valid}"
                )
    return errors

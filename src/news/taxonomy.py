"""Сквозная смена direction/category у новостей и пересказов (ds_search#543).

SQLite news_items + PATCH метаданных в GAR (если запись уже загружена).
Категория валидируется по направлению через живую схему GAR (ADR-013).
"""
from __future__ import annotations

from . import db


def validate(direction: str, category: str) -> None:
    """ValueError, если direction/category не из схемы GAR или не согласованы."""
    from ..metadata import gar_schema
    fields = gar_schema.load_gar_schema()
    if direction not in gar_schema.field_options(fields, "direction"):
        raise ValueError(f"неизвестное направление: {direction}")
    if category and category not in gar_schema.category_options_for_direction(fields, direction):
        raise ValueError(f"категория {category} не относится к направлению {direction}")


def _patch_gar(document_id: str, updates: dict) -> None:
    from ..gar_ingest.client import GarIngestClient, load_settings
    with GarIngestClient(load_settings()) as client:
        client.patch_document_metadata(document_id, updates)


def apply_taxonomy(items: list[dict], direction: str, category: str,
                   patch_fn=_patch_gar) -> tuple[int, list[str]]:
    """Возвращает (успешно, ошибки). Сначала GAR, потом SQLite: при ошибке
    PATCH локальная запись не меняется, чтобы не расходиться с GAR."""
    validate(direction, category)
    updates = {"direction": direction, "category": category or None}
    ok, errors = 0, []
    for item in items:
        try:
            if item.get("gar_document_id"):
                patch_fn(item["gar_document_id"], updates)
            db.update_news_item(item["id"], updates)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{item.get('title') or item['id']}: {exc}")
    return ok, errors

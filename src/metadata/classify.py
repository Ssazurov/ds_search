"""LLM-классификатор select-полей metadata (age/target_audience/direction/
category/doc_type) по тексту статьи (issue #91, эпик #88).

Промпт собирается динамически из активной схемы GAR (gar_schema.py) —
модель выбирает значения строго из списка допустимых опций, не выдумывает
свои. При ошибке/таймауте LLM или невалидном ответе -> fallback на
per-source дефолты (gar_mapping.py, issue #90); поле, не закрытое ни LLM,
ни дефолтом, остаётся None -> needs_review=True (интеграция — issue #93).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import gar_mapping, gar_schema
from ..news.llm_draft import LlmConfig, call_llm, parse_llm_json

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "classify_llm.yaml"

# category — dependent (см. build_prompt/_validate_against_schema), в общий
# список независимых select-полей не входит.
_SELECT_FIELDS = ["age", "target_audience", "direction", "doc_type"]
_ALL_FIELDS = [*_SELECT_FIELDS, "category"]
_TEXT_LIMIT = 4000  # символов текста статьи в промпте — экономия токенов LLM


def load_llm_config(path: Path = CONFIG_PATH) -> LlmConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LlmConfig(
        provider=data["provider"],
        model=data["model"],
        endpoint=data["endpoint"],
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens", 400)),
        prompt_template="",
        timeout_s=float(data.get("timeout_s", 30.0)),
    )


def build_prompt(fields: dict, title: str | None, text: str | None) -> str:
    """Промпт со списком допустимых опций по каждому select-полю, собранным
    из актуальной схемы GAR (fields — результат gar_schema.load_gar_schema())."""
    lines = [
        "Определи значения полей метаданных для статьи. Отвечай ТОЛЬКО JSON,",
        "без markdown-обрамления и пояснений. Для каждого поля выбери РОВНО",
        "одно значение из списка допустимых или null, если по тексту не",
        "определить однозначно (не выдумывай значения вне списка).",
        "",
    ]
    for key in _SELECT_FIELDS:
        options = gar_schema.field_options(fields, key)
        if options:
            lines.append(f"{key}: [{', '.join(options)}]")

    direction_field = next((f for f in fields.get("fields", []) if f["key"] == "direction"), None)
    categories: list[str] = []
    if direction_field:
        for opt in direction_field.get("options", []):
            categories.extend(gar_schema.category_options_for_direction(fields, opt["value"]))
    if categories:
        lines.append(f"category (зависит от direction): [{', '.join(sorted(set(categories)))}]")

    lines += [
        "",
        f"Заголовок: {title or ''}",
        "Текст статьи:",
        "---",
        (text or "")[:_TEXT_LIMIT],
        "---",
        "",
        'Верни JSON строго формата: {"age": ..., "target_audience": ..., '
        '"direction": ..., "category": ..., "doc_type": ...}',
    ]
    return "\n".join(lines)


def _validate_against_schema(result: dict, fields: dict) -> dict:
    """Обнулить значения вне допустимых опций схемы (модель могла всё равно
    их выдумать) — лучше None -> needs_review, чем невалидное значение в GAR."""
    clean = dict(result)
    for key in _SELECT_FIELDS:
        valid = gar_schema.field_options(fields, key)
        if valid and clean.get(key) not in valid:
            clean[key] = None
    direction = clean.get("direction")
    valid_categories = gar_schema.category_options_for_direction(fields, direction) if direction else []
    if valid_categories and clean.get("category") not in valid_categories:
        clean["category"] = None
    if not direction:
        clean["category"] = None
    return clean


def classify(
    title: str | None,
    text: str | None,
    fields: dict,
    *,
    domain: str | None = None,
    dest_dir: str | None = None,
    config: LlmConfig | None = None,
    mapping: dict | None = None,
) -> dict:
    """Возвращает {age, target_audience, direction, category, doc_type,
    needs_review, source}. source: "llm" | "llm+fallback" | "fallback" |
    "none". needs_review=True, если хоть одно поле осталось None после LLM
    и per-source дефолтов (gar_mapping.py, issue #90)."""
    result: dict = {k: None for k in _ALL_FIELDS}
    source = "none"

    try:
        cfg = config or load_llm_config()
        prompt = build_prompt(fields, title, text)
        raw = call_llm(prompt, cfg)
        parsed = parse_llm_json(raw)
        result.update({k: parsed.get(k) for k in _ALL_FIELDS})
        result = _validate_against_schema(result, fields)
        source = "llm"
    except Exception:
        result = {k: None for k in _ALL_FIELDS}

    if domain:
        missing_before = {k for k, v in result.items() if v is None}
        if missing_before:
            defaults = gar_mapping.resolve_defaults(domain, dest_dir, mapping=mapping)
            for key in missing_before:
                if key in defaults:
                    result[key] = defaults[key]
            applied = missing_before & defaults.keys()
            if applied:
                source = "llm+fallback" if source == "llm" else "fallback"

    result["needs_review"] = any(v is None for v in result.values())
    result["source"] = source
    return result

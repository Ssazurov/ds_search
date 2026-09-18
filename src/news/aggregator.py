"""Извлечение ссылки на первоисточник из уже скачанного текста статьи
агрегатора (ADR-0012 `ds_search/docs/adr/0012-aggregator-source-detection.md`,
issue #194).

Первоисточник НЕ краулится — его домен не обязан быть в
config/licenses.yaml. Ссылка используется только для атрибуции в
news_items.source_url; текст/summary остаются на основе текста агрегатора.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

# markdown-ссылка вида "Источник: [домен](url)" (wildcar.ru и подобные
# агрегаторы ставят её последней строкой перед футером/подпиской).
_SOURCE_LINE_RE = re.compile(
    r"(?:Источник|Source|Fonte)\s*:\s*\[[^\]]*\]\((https?://[^\s)]+)\)",
    re.IGNORECASE,
)


def extract_primary_source_url(text: str) -> str | None:
    """Возвращает URL первоисточника из строки "Источник: [домен](url)"
    в тексте статьи агрегатора, либо None, если такой строки нет."""
    match = _SOURCE_LINE_RE.search(text)
    if not match:
        return None
    return match.group(1)


def primary_source_domain(url: str) -> str:
    return urlsplit(url).netloc.lower()

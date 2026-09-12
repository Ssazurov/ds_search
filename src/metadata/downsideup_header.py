"""Парсинг текстовой шапки статей downsideup.org (дата/описание/автор),
которую markdown-генератор сохраняет как часть текста статьи, а не в
HTML og:*-метатегах (extract_page_meta их не видит). Формат шапки:

    30.12.2020 2260
    # Название статьи
    #### Описание:
    Текст описания...
      * #### Источник:      (опциональное поле, может отсутствовать)
    [ Журнал ... ](url)
      * #### Автор:
    [ Имя автора](url), [ Второе имя](url)

    Текст статьи...

Между "Описание" и "Автор" может быть произвольный набор доп.полей
(например "Источник:") — они пропускаются, для парсинга важны только
"Описание" и "Автор". Перед строкой с датой могут быть хлебные крошки
и/или баннер "нужна регистрация" (crawl4ai иногда их не фильтрует).
"""
from __future__ import annotations

import re

_AUTHOR_LINK_RE = re.compile(r"\[\s*([^\]]+?)\s*\]\([^)]*\)")
_HEADING_RE = re.compile(r"^\s*(?:\*\s*)?####\s*(.+?)\s*:?\s*$")
_MAX_PREFIX_LINES = 5  # хлебные крошки / баннер регистрации перед датой


def _to_iso(date_str: str) -> str:
    dd, mm, yyyy = date_str.split(".")
    return f"{yyyy}-{mm}-{dd}"


def parse_header(markdown: str) -> tuple[dict, str]:
    """Вернуть (meta, markdown_без_шапки). meta пуст, если шапки нет."""
    lines = markdown.split("\n")
    date_idx = None
    m = None
    for idx, line in enumerate(lines[:_MAX_PREFIX_LINES]):
        m = re.match(r"^(\d{2}\.\d{2}\.\d{4})\b", line)
        if m:
            date_idx = idx
            break
    if date_idx is None or date_idx + 1 >= len(lines) or not lines[date_idx + 1].lstrip().startswith("#"):
        return {}, markdown

    publish_date = _to_iso(m.group(1))
    i = date_idx + 2
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    fields: dict[str, str] = {}
    while i < len(lines):
        hm = _HEADING_RE.match(lines[i])
        if not hm:
            break
        field_name = hm.group(1).strip().lower()
        i += 1
        content_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "" and not _HEADING_RE.match(lines[i]):
            content_lines.append(lines[i])
            i += 1
        fields[field_name] = "\n".join(content_lines).strip()

    if "описание" not in fields:
        return {"publish_date": publish_date}, "\n".join(lines[date_idx + 1:]).lstrip("\n")

    description = fields.get("описание", "")
    author = ""
    if "автор" in fields:
        names = _AUTHOR_LINK_RE.findall(fields["автор"])
        author = ", ".join(n.strip() for n in names if n.strip())

    while i < len(lines) and lines[i].strip() == "":
        i += 1
    body = "\n".join(lines[i:])
    return {"publish_date": publish_date, "description": description, "author": author}, body

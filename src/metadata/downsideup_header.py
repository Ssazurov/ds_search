"""Парсинг текстовой шапки статей downsideup.org (дата/описание/автор),
которую markdown-генератор сохраняет как часть текста статьи, а не в
HTML og:*-метатегах (extract_page_meta их не видит). Формат шапки:

    30.12.2020 2260
    # Название статьи
    #### Описание:
    Текст описания...
      * #### Автор:
    [ Имя автора](url), [ Второе имя](url)

    Текст статьи...
"""
from __future__ import annotations

import re

_AUTHOR_LINK_RE = re.compile(r"\[\s*([^\]]+?)\s*\]\([^)]*\)")


def _to_iso(date_str: str) -> str:
    dd, mm, yyyy = date_str.split(".")
    return f"{yyyy}-{mm}-{dd}"


def parse_header(markdown: str) -> tuple[dict, str]:
    """Вернуть (meta, markdown_без_шапки). meta пуст, если шапки нет."""
    lines = markdown.split("\n")
    if not lines:
        return {}, markdown
    m = re.match(r"^(\d{2}\.\d{2}\.\d{4})\b", lines[0])
    if not m or len(lines) < 2 or not lines[1].lstrip().startswith("#"):
        return {}, markdown

    publish_date = _to_iso(m.group(1))
    i = 2
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or "Описание" not in lines[i]:
        return {"publish_date": publish_date}, "\n".join(lines[1:]).lstrip("\n")

    i += 1
    desc_lines: list[str] = []
    while i < len(lines) and "Автор" not in lines[i]:
        desc_lines.append(lines[i])
        i += 1
    description = "\n".join(desc_lines).strip()

    author = ""
    if i < len(lines):  # нашли строку "Автор:"
        i += 1
        author_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "":
            author_lines.append(lines[i])
            i += 1
        names = _AUTHOR_LINK_RE.findall(" ".join(author_lines))
        author = ", ".join(n.strip() for n in names if n.strip())

    while i < len(lines) and lines[i].strip() == "":
        i += 1
    body = "\n".join(lines[i:])
    return {"publish_date": publish_date, "description": description, "author": author}, body

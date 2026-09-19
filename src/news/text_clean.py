"""Очистка markdown-текста статьи перед LLM-черновиком (issue #208).

crawl4ai fit_markdown часто содержит шапку (навигация, «Версия для печати»,
«Далее в сюжете») и подвал (подписки, теги, «Последние новости», списки
ссылок). Это съедает контекст модели и приводит к галлюцинациям, поэтому
в LLM уходит только тело статьи. Эвристики — по маркерам, не по сайту.
Если после очистки остаётся слишком мало текста, возвращаем исходный
(обрезанный) — лучше шум, чем пустой вход.
"""
from __future__ import annotations

import re

MAX_CHARS = 6000  # ~3K токенов для кириллицы; вместе с промптом влезает в num_ctx 8192
MIN_BODY_CHARS = 300  # до этого объёма текста маркеры подвала не считаются подвалом
MIN_RESULT_CHARS = 200

_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\((?:[^()\s]|\([^)]*\))*\)")
_LINK_ITEM = re.compile(r"^\s*(?:[*+-]|\d+\.)\s+.*\]\(https?://")
_LONE_LINK = re.compile(r"^\s*\[[^\]]*\]\(https?://[^)]*\)\s*$")
_FOOTER = re.compile(
    r"^(подпишитесь|читайте нас|читайте также|читайте ещ|смотрите также|"
    r"поделиться|ранее в|последние новости|актуальные темы|похожие|"
    r"другие новости|все новости|популярное|самое читаемое|комментарии|"
    r"related|share|comments)",
    re.IGNORECASE,
)
_NOISE = re.compile(
    r"^(версия для печати|далее в сюжете|распечатать|печать)\b", re.IGNORECASE
)
_PHOTO = re.compile(r"^[_\s|*]*фото\s*:", re.IGNORECASE)
_STRIP = "#*_>[ \t"


def _key(line: str) -> str:
    return line.strip(_STRIP).strip()


def _is_link_item(raw: str) -> bool:
    return bool(_LINK_ITEM.match(raw))


def clean_article_text(text: str, max_chars: int = MAX_CHARS) -> str:
    original = text.strip()
    raw_lines = _IMG.sub("", text).splitlines()

    # 1. подвал: первый маркер или блок из >=3 подряд ссылок-пунктов
    #    после того, как накопилось достаточно тела статьи
    body_len = 0
    cut = len(raw_lines)
    for i, raw in enumerate(raw_lines):
        line = _LINK.sub(r"\1", raw)
        k = _key(line)
        if body_len >= MIN_BODY_CHARS:
            if k and len(k) <= 120 and _FOOTER.match(k):
                cut = i
                break
            if (_is_link_item(raw) and i + 2 < len(raw_lines)
                    and all(_is_link_item(x) for x in raw_lines[i:i + 3])):
                cut = i
                break
        if k and not _is_link_item(raw) and not _LONE_LINK.match(raw):
            body_len += len(k)
    lines = raw_lines[:cut]

    # 2. шапка/шум: навигационные ссылки до первого абзаца, «Версия для печати», подписи к фото
    out: list[str] = []
    seen_paragraph = False
    for raw in lines:
        line = _LINK.sub(r"\1", raw).rstrip()
        k = _key(line)
        if not k:
            out.append("")
            continue
        if _NOISE.match(k) or _PHOTO.match(k):
            continue
        if not seen_paragraph and (_is_link_item(raw) or _LONE_LINK.match(raw)):
            continue
        if len(k) >= 80 and not k.startswith("#"):
            seen_paragraph = True
        out.append(line)

    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    if len(cleaned) < MIN_RESULT_CHARS:
        cleaned = original
    if len(cleaned) > max_chars:
        head = cleaned[:max_chars]
        nl = head.rfind("\n")
        cleaned = head[:nl] if nl > max_chars // 2 else head
    return cleaned

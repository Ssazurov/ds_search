"""issue #569: единый резолвер автора статьи.

Порядок: уже найденный (meta/шапка/тело) -> HTML (JSON-LD, «Автор:») ->
LLM (только если пусто, имя должно встречаться в тексте) -> название сайта.
Отдельного поля author_kind нет: фолбэк — просто имя сайта в author.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
from pathlib import Path
from typing import Callable

import yaml

from .meta_extract import extract_meta_tags

logger = logging.getLogger(__name__)

SITE_AUTHORS_PATH = Path(__file__).resolve().parents[2] / "config" / "site_authors.yaml"

# «Автор:» с двоеточием (не «Авторы исследования», не «Авторизация»);
# между двоеточием и именем могут быть теги (<a ...>).
_HTML_AUTHOR_RE = re.compile(r"Авторы?\s*:\s*(?:<[^>]+>\s*)*([^<]{2,150})")
_JSONLD_RE = re.compile(r'"author"\s*:\s*(?:\[\s*)?\{[^{}]*?"name"\s*:\s*"([^"]{2,150})"')
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(name: str) -> str:
    name = html_lib.unescape(_TAG_RE.sub("", name))
    name = re.sub(r"\s+", " ", name).strip(" \t\n,;:_*")
    return name


def _is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))


def author_from_html(html: str) -> str:
    """Автор из сырого HTML: JSON-LD, затем «Автор: <a>Имя</a>»."""
    if not html:
        return ""
    m = _JSONLD_RE.search(html)
    if m:
        name = _clean(m.group(1))
        if name and not _is_url(name):
            return name
    for m in _HTML_AUTHOR_RE.finditer(html):
        name = _clean(m.group(1))
        if name and not _is_url(name):
            return name
    return ""


def _load_site_authors(path: Path = SITE_AUTHORS_PATH) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def site_fallback(domain: str, site_name: str = "", html: str = "",
                  site_authors: dict | None = None) -> str:
    """Название сайта как автор: config/site_authors.yaml -> site_name реестра -> og:site_name."""
    mapping = site_authors if site_authors is not None else _load_site_authors()
    d = (domain or "").lower().removeprefix("www.")
    if mapping.get(d):
        return str(mapping[d]).strip()
    if (site_name or "").strip():
        return site_name.strip()
    return extract_meta_tags(html).get("og:site_name", "").strip()


_LLM_PROMPT = (
    "Ниже начало и конец статьи. Найди автора-человека (ФИО), если он указан в тексте. "
    "Не выдумывай. Ответь только именем автора или словом NONE.\n\n{text}"
)


def _names_in_text(name: str, text: str) -> bool:
    return all(tok in text for tok in re.findall(r"\w{2,}", name))


def default_author_llm(markdown: str) -> str:
    """LLM-проверка (конфиг classify_llm.yaml). Выключается DS_AUTHOR_LLM=0."""
    if os.environ.get("DS_AUTHOR_LLM", "1") == "0" or not markdown:
        return ""
    try:
        from ..news.llm_draft import call_llm
        from .classify import load_llm_config

        text = markdown if len(markdown) <= 3000 else markdown[:1500] + "\n...\n" + markdown[-1500:]
        raw = call_llm(_LLM_PROMPT.format(text=text), load_llm_config(), purpose="author", input_chars=len(text))
    except Exception as exc:  # noqa: BLE001 — LLM не должен ронять загрузку
        logger.warning("author LLM failed: %s", exc)
        return ""
    answer = _clean((raw or "").strip().splitlines()[0] if (raw or "").strip() else "")
    if not answer or answer.upper() == "NONE" or len(answer.split()) > 8:
        return ""
    return answer if _names_in_text(answer, markdown) else ""


def resolve_author(
    current: str = "", *, html: str = "", markdown: str = "", domain: str = "",
    site_name: str = "", llm: Callable[[str], str] | None = default_author_llm,
    site_authors: dict | None = None,
) -> str:
    """Вернуть автора; пустую строку не возвращает, если известно имя сайта."""
    current = (current or "").strip()
    if current and not _is_url(current):
        return current
    found = author_from_html(html)
    if not found and llm:
        found = llm(markdown)
    if found:
        return found
    return site_fallback(domain, site_name, html, site_authors)

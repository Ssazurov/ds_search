"""issue #92: author/publish_date/description из og:*/meta-тегов, без LLM.

Использует result.metadata, который crawl4ai уже собирает из HTML (og:*,
article:*, name=description/author) — здесь только приоритет и нормализация
под sidecar-схему (issue #33).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

# issue #569: допускаем markdown-обрамление (_Автор:__Имя_, **Автор:** Имя)
_AUTHOR_LINE_RE = re.compile(r"^[\s_*>]*Авторы?\s*:[\s_*]*(.+?)[\s_]*$", re.MULTILINE)
_ROLE_SPLIT_RE = re.compile(r"\s+[-–—]\s+")

_META_KEYS = {
    "article:published_time", "og:published_time", "article:modified_time",
    "og:description", "description", "twitter:description", "author",
    "article:author", "twitter:creator", "og:site_name",
}


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        key = (a.get("property") or a.get("name") or "").strip().lower()
        content = a.get("content", "").strip()
        if key in _META_KEYS and content and key not in self.meta:
            self.meta[key] = content


def extract_meta_tags(html: str) -> dict:
    """issue #355: <meta property|name=... content=...> из сырого HTML -> dict
    для extract_page_meta (probe не получает crawl4ai result.metadata).
    Ключи регистронезависимы, берётся первое вхождение."""
    parser = _MetaParser()
    try:
        parser.feed(html or "")
    except Exception:  # noqa: BLE001 — битый HTML не должен ронять probe
        pass
    return parser.meta


def extract_author_from_markdown(markdown: str) -> str:
    """Извлечь автора вместе с markdown-ссылкой из строки ``Автор:``."""
    m = _AUTHOR_LINE_RE.search(markdown or "")
    if not m:
        return ""
    line = m.group(1).split("Журнал:")[0]
    line = _ROLE_SPLIT_RE.split(line, maxsplit=1)[0]  # «Имя - редактор сайта …» -> «Имя»
    return line.strip(" ,;_*")


def extract_page_meta(metadata: dict | None, markdown: str = "") -> dict:
    """Вернуть {author, publish_date, description} (пустая строка, если нет)."""
    metadata = metadata or {}

    description = (
        metadata.get('og:description')
        or metadata.get('description')
        or metadata.get('twitter:description')
        or ''
    ).strip()

    author = (
        metadata.get('article:author')
        or metadata.get('author')
        or metadata.get('twitter:creator')
        or ''
    ).strip()

    # issue #338: article:author у части сайтов — ссылка на соцсеть издания
    # (facebook.com/foma.ru), не автор. Реальный автор — из тела статьи.
    body_author = extract_author_from_markdown(markdown)
    if body_author:
        author = body_author
    elif author.lower().startswith(("http://", "https://")):
        author = ""

    publish_date = (
        metadata.get('article:published_time')
        or metadata.get('og:published_time')
        or metadata.get('article:modified_time')
        or ''
    ).strip()

    return {'author': author, 'publish_date': publish_date, 'description': description}


def strip_site_suffix(title: str | None, site_name: str | None) -> str:
    """Срезает с конца <title> «<разделитель> <site_name>» (напр. « - Православный
    журнал «Фома»»). site_name задаётся в реестре домена (issue #347); пусто —
    title не меняется."""
    title = (title or "").strip()
    name = (site_name or "").strip()
    if not name:
        return title
    m = re.match(r"^(.*?)\s*[-–—|:·•]\s*" + re.escape(name) + r"\s*$", title, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m and m.group(1).strip() else title

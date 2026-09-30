"""Транслит заголовка в slug для имени файла (issue #388, ГОСТ 7.79 сист. B, упрощённо)."""
from __future__ import annotations

import re

_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "shh", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify(title: str, max_len: int = 80) -> str:
    """Пустая строка, если из заголовка не получилось ни одного символа."""
    out = "".join(_MAP.get(c, c) for c in title.lower())
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out[:max_len].strip("-")


def domain_dirname(netloc: str) -> str:
    """Безопасное имя папки из host: lower, без порта, только [a-z0-9.-]."""
    host = netloc.lower().split("@")[-1].split(":")[0]
    return re.sub(r"[^a-z0-9.-]", "", host).strip(".") or "unknown"


def norm_domain(domain: str) -> str:
    """Каноничный домен источника: lower, без порта и без ведущего www. (issue #400)."""
    host = (domain or "").lower().strip().split("@")[-1].split(":")[0]
    return host.removeprefix("www.")

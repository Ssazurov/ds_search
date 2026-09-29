"""Разбор даты публикации из ответов поисковых провайдеров (ds_search #355)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

_REL_RE = re.compile(
    r"^\s*(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago\s*$", re.IGNORECASE
)
_REL_UNITS = {
    "second": timedelta(seconds=1),
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def parse_published(value: str | None, now: datetime | None = None) -> datetime | None:
    """ISO-8601, RFC-2822 или относительная строка Brave ('3 days ago') -> tz-aware UTC.

    Пустое или нераспознанное значение -> None, исключений не бросает."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    m = _REL_RE.match(text)
    if m:
        base = _utc(now) if now else datetime.now(timezone.utc)
        return base - int(m.group(1)) * _REL_UNITS[m.group(2).lower()]
    try:
        return _utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        pass
    try:
        return _utc(parsedate_to_datetime(text))
    except (TypeError, ValueError):
        return None

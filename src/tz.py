"""Время в МСК (+3 ч) для вывода в UI. Хранение — UTC; naive-значения считаются UTC.
Фиксированное смещение (в РФ нет перехода на летнее время) — без зависимости от tzdata."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3), "MSK")
FMT = "%d.%m.%Y %H:%M"
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse(value) -> datetime | None:
    if value is None or value == "":
        return None
    if hasattr(value, "to_pydatetime"):  # pd.Timestamp / NaT
        try:
            if value != value:  # NaT
                return None
            value = value.to_pydatetime()
        except (ValueError, TypeError):
            return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def msk_naive(value) -> datetime | None:
    """Значение (UTC/aware/ISO-строка) → naive datetime в МСК. Строка «ГГГГ-ММ-ДД» (только дата) не сдвигается."""
    if isinstance(value, str) and _DATE_ONLY.match(value.strip()):
        return datetime.fromisoformat(value.strip())
    dt = _parse(value)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK).replace(tzinfo=None)


def fmt_msk(value, empty: str = "—") -> str:
    """«06.10.2026 10:21» (МСК, без суффикса)."""
    dt = msk_naive(value)
    return dt.strftime(FMT) if dt else empty


def msk_to_utc_naive(dt: datetime) -> datetime:
    """Введённое пользователем время (МСК, naive) → naive UTC для запросов/хранения."""
    return dt.replace(tzinfo=MSK).astimezone(timezone.utc).replace(tzinfo=None)


def now_msk() -> datetime:
    return datetime.now(timezone.utc).astimezone(MSK).replace(tzinfo=None)


def msk_series(series):
    """pd.Series любых дат → datetime64 в МСК (naive); нераспознанное → NaT."""
    import pandas as pd
    return pd.to_datetime(pd.Series([msk_naive(v) for v in series], index=series.index), errors="coerce")

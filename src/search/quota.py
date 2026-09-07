"""Файловый счётчик расхода квоты провайдера (issue #15, ADR-002).

Простой JSON-стейт вместо БД — соответствует MVP-масштабу (один
проект, локальный запуск). period="daily"|"monthly".
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


def _period_key(period: str, today: date) -> str:
    if period == "daily":
        return today.isoformat()
    return today.strftime("%Y-%m")  # monthly


@dataclass
class QuotaState:
    path: Path
    provider: str
    limit: int
    period: str = "monthly"  # "daily" | "monthly"

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def used(self) -> int:
        data = self._load()
        key = _period_key(self.period, date.today())
        return data.get(self.provider, {}).get(key, 0)

    def has_quota(self, cost: int = 1) -> bool:
        return self.used() + cost <= self.limit

    def record(self, cost: int = 1) -> None:
        data = self._load()
        key = _period_key(self.period, date.today())
        bucket = data.setdefault(self.provider, {})
        bucket[key] = bucket.get(key, 0) + cost
        self._save(data)

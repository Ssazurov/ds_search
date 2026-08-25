"""Проверка лицензии/ToS источника перед скачиванием (issue #3, ADR-001 п.3).

Работает в две ступени:
1. Автоматическая — robots.txt источника (если явно запрещает обход
   нашим user-agent, статус deny без обращения к реестру).
2. Реестр `config/licenses.yaml` — результат ручного юридического анализа
   ToS/подвала сайта по каждому домену (allow / attribution_required / deny).
   Автоматический парсинг произвольного текста ToS ненадёжен для MVP,
   поэтому это ручной, но обязательный шаг (см. ADR-001 п.3).

Домен, которого нет в реестре, получает статус pending_manual_review и
трактуется краулером как "не скачивать" — безопасный дефолт до тех пор,
пока источник не будет вручную проверен и добавлен в реестр.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx
import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "licenses.yaml"
_DEFAULT_USER_AGENT = "ds-search-bot"


class LicenseStatus(str, Enum):
    ALLOW = "allow"
    ATTRIBUTION_REQUIRED = "attribution_required"
    DENY = "deny"
    PENDING_MANUAL_REVIEW = "pending_manual_review"


@dataclass
class LicenseCheckResult:
    status: LicenseStatus
    reason: str
    attribution_template: str | None = None

    @property
    def downloadable(self) -> bool:
        return self.status in (LicenseStatus.ALLOW, LicenseStatus.ATTRIBUTION_REQUIRED)

    def build_attribution(self, *, title: str, source_url: str) -> str | None:
        if not self.attribution_template:
            return None
        return self.attribution_template.format(title=title, source_url=source_url)


def _load_registry(path: Path = _CONFIG_PATH) -> dict:
    if not path.exists():
        logger.warning("licenses.yaml не найден (%s) — реестр пуст", path)
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _check_robots(base_url: str, user_agent: str) -> bool | None:
    """True/False — явное разрешение/запрет, None — robots.txt недоступен."""
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        resp = httpx.get(robots_url, timeout=10, follow_redirects=True)
        if resp.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser.can_fetch(user_agent, base_url)
    except httpx.HTTPError as exc:
        logger.warning("robots.txt недоступен для %s: %s", robots_url, exc)
        return None


def check_license(
    domain: str,
    base_url: str,
    user_agent: str = _DEFAULT_USER_AGENT,
    registry_path: Path = _CONFIG_PATH,
) -> LicenseCheckResult:
    robots_ok = _check_robots(base_url, user_agent)
    if robots_ok is False:
        return LicenseCheckResult(
            status=LicenseStatus.DENY,
            reason="robots.txt запрещает обход для нашего user-agent",
        )

    registry = _load_registry(registry_path)
    entry = registry.get(domain)
    if entry is None:
        return LicenseCheckResult(
            status=LicenseStatus.PENDING_MANUAL_REVIEW,
            reason=(
                f"домен {domain} отсутствует в config/licenses.yaml — "
                "требуется ручная проверка ToS перед автосбором"
            ),
        )

    status = LicenseStatus(entry["status"])
    reason = entry.get("notes", "статус из config/licenses.yaml")
    return LicenseCheckResult(
        status=status,
        reason=reason,
        attribution_template=entry.get("attribution_template"),
    )

"""Проверка лицензии/ToS источника перед скачиванием (issue #3, ADR-001 п.3).

Работает в две ступени:
1. Автоматическая — robots.txt источника (если явно запрещает обход
   нашим user-agent, статус deny без обращения к реестру).
2. Реестр источников (БД GAR, ds ADR-0021) — результат ручного юридического
   анализа ToS/подвала сайта по каждому домену (allow / attribution_required / deny).
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
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .registry_store import GarRegistryStore

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = "ds-search-bot"


class LicenseStatus(str, Enum):
    ALLOW = "allow"
    ATTRIBUTION_REQUIRED = "attribution_required"
    DENY = "deny"
    PENDING_MANUAL_REVIEW = "pending_manual_review"


class PublishPermission(str, Enum):
    """Разрешение на публикацию материалов источника на внешнем сайте
    (issue #224, ADR-0018 п.3). Хранится по домену в реестре, ОТДЕЛЬНО от
    `status` лицензии (ADR-0013): статус — можно ли скачать, разрешение —
    можно ли выложить публично."""

    NOT_SET = "not_set"
    NOT_REQUIRED = "not_required"
    GRANTED = "granted"
    DENIED = "denied"


PUBLISH_PERMISSION_LABELS = {
    PublishPermission.NOT_SET: "Не выбрано",
    PublishPermission.NOT_REQUIRED: "Разрешение не требуется",
    PublishPermission.GRANTED: "Разрешение получено",
    PublishPermission.DENIED: "Разрешение запрещено",
}


def parse_publish_permission(value: object) -> PublishPermission:
    """Отсутствующее/неизвестное значение (старые записи реестра) → not_set."""
    try:
        return PublishPermission(value)
    except ValueError:
        return PublishPermission.NOT_SET


@dataclass
class LicenseCheckResult:
    status: LicenseStatus
    reason: str
    attribution_template: str | None = None
    is_aggregator: bool = False
    publish_permission: PublishPermission = PublishPermission.NOT_SET

    @property
    def downloadable(self) -> bool:
        return self.status in (LicenseStatus.ALLOW, LicenseStatus.ATTRIBUTION_REQUIRED)

    def build_attribution(self, *, title: str, source_url: str) -> str | None:
        if not self.attribution_template:
            return None
        return self.attribution_template.format(title=title, source_url=source_url)


def normalize_domain(domain: str) -> str:
    """Канонический ключ реестра: lower, без порта и ведущего 'www.'
    (issue #206). Без этого www.example.org и example.org считались разными
    доменами, и ссылка на www-адрес блокировалась как pending_manual_review."""
    d = domain.strip().lower()
    if "://" in d:
        d = urlsplit(d).netloc
    d = d.rsplit("@", 1)[-1].split(":", 1)[0]
    return d[4:] if d.startswith("www.") else d


def default_attribution_template(domain: str) -> str:
    """Шаблон атрибуции по умолчанию для нового источника."""
    return f"Источник: {{title}} ({{source_url}}), {domain}"


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
    registry_store=None,
) -> LicenseCheckResult:
    """Реестр источников — в GAR (+ кэш при недоступности), ds ADR-0021 (#263).
    `registry_store` для тестов (см. tests/test_registry_store.py,
    tests/test_license_checker.py); в проде всегда GarRegistryStore()."""
    robots_ok = _check_robots(base_url, user_agent)
    if robots_ok is False:
        return LicenseCheckResult(
            status=LicenseStatus.DENY,
            reason="robots.txt запрещает обход для нашего user-agent",
        )

    domain = normalize_domain(domain)
    store = registry_store if registry_store is not None else GarRegistryStore()
    entry = store.get(domain)
    if entry is None:
        store.ensure(domain, default_attribution_template(domain))
        return LicenseCheckResult(
            status=LicenseStatus.PENDING_MANUAL_REVIEW,
            reason=(
                f"домен {domain} отсутствует в реестре источников (или реестр GAR недоступен) — "
                "требуется ручная проверка ToS перед автосбором"
            ),
        )

    status = LicenseStatus(entry["status"])
    reason = entry.get("notes", "статус из реестра источников")
    return LicenseCheckResult(
        status=status,
        reason=reason,
        attribution_template=entry.get("attribution_template"),
        is_aggregator=bool(entry.get("is_aggregator", False)),
        publish_permission=parse_publish_permission(entry.get("publish_permission")),
    )

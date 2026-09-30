"""Добавление одного документа по известному URL через админку (ADR-0014,
issue #204). Переиспользует SourceCrawler.recrawl_url() — тот же staged
single-URL crawl, что и reload (ADR-0007/0009): crawl -> staging, не прямая
запись без проверки. Identity — canonical_url (ADR-0010),
doc_id = sha256(canonical_url)[:16].

Дубликат по canonical_url отклоняется — нужно использовать reload-flow
(ADR-0007/0009) для обновления уже существующего документа, новый sidecar
не создаётся. Неизвестный домен получает pending_manual_review в реестре
источников (license gate, ADR-0013/0021) — сохранение sidecar
блокируется до ручного статуса.

Папка = домен: сконфигурированный источник (SOURCES) — его обычная папка
data/raw/<source>/, иначе data/raw/<domain>/ (issue #388, ранее manual/).
Имя файла — транслит заголовка (коллизия -> суффикс _YYYYMMDD-HHMMSS).
Дубликат ищется по source_url во всех data/raw/*/*.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from ..license.checker import LicenseStatus, check_license
from .config import SOURCES, SourceConfig
from .crawler import SourceCrawler
from .filters import canonicalize_url
from .slug import domain_dirname, norm_domain

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"
MANUAL_SOURCE_NAME = "manual"


def _resolve_source(domain: str, data_root: Path) -> tuple[SourceConfig, Path]:
    """Существующий source по домену -> его папка data/raw/<name>;
    иначе data/raw/<domain>/ (issue #388)."""
    cfg = next((c for c in SOURCES.values() if c.domain == domain), None)
    if cfg is not None:
        return cfg, data_root / cfg.name
    name = domain_dirname(domain)
    return SourceConfig(name=name, domain=domain, seed_urls=[], keywords=[]), data_root / name


def _find_existing(canon: str, doc_id: str, data_root: Path) -> Path | None:
    """Дубликат по canonical_url (не по имени файла): hash-имя или source_url в sidecar."""
    for p in data_root.glob(f"*/{doc_id}.json"):
        return p
    for p in data_root.glob("*/*.json"):
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("source_url") == canon:
                return p
        except (OSError, ValueError, AttributeError):
            continue
    return None


async def add_manual_document(
    url: str,
    data_root: Path = DATA_ROOT,
    *,
    dest_dir: str | None = None,
    filename: str | None = None,
    direction: str | None = None,
    category: str | None = None,
) -> dict:
    """Возвращает dict со статусом:
    - 'added' — sidecar сохранён; 'doc_id', 'meta', 'source' в результате.
    - 'duplicate' — canonical_url уже есть в корпусе; 'doc_id', 'path'.
    - 'license_pending' / 'license_denied' — license gate не пропустил; 'reason'.
    - 'failed' — скачивание не удалось или контент отклонён (thin/каталог); 'reason'.
    """
    canon = canonicalize_url(url)
    domain = norm_domain(urlparse(canon).netloc)
    cfg, out_dir = _resolve_source(domain, data_root)
    doc_id = hashlib.sha256(canon.encode()).hexdigest()[:16]

    existing = _find_existing(canon, doc_id, data_root)
    if existing is not None:
        return {"status": "duplicate", "doc_id": doc_id, "path": str(existing)}

    license_result = check_license(cfg.domain, url)
    if not license_result.downloadable:
        status = (
            "license_pending"
            if license_result.status == LicenseStatus.PENDING_MANUAL_REVIEW
            else "license_denied"
        )
        return {"status": status, "reason": license_result.reason}

    crawler = SourceCrawler(cfg, out_dir)
    meta = await crawler.recrawl_url(
        url, dest_dir=dest_dir, filename=filename, direction=direction, category=category,
        slug_from_title=True,
    )
    if meta is None:
        return {
            "status": "failed",
            "reason": "не удалось скачать страницу или контент отклонён (thin content/каталог-листинг)",
        }
    return {"status": "added", "doc_id": doc_id, "meta": meta, "source": cfg.name}

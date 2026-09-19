"""Добавление одного документа по известному URL через админку (ADR-0014,
issue #204). Переиспользует SourceCrawler.recrawl_url() — тот же staged
single-URL crawl, что и reload (ADR-0007/0009): crawl -> staging, не прямая
запись без проверки. Identity — canonical_url (ADR-0010),
doc_id = sha256(canonical_url)[:16].

Дубликат по canonical_url отклоняется — нужно использовать reload-flow
(ADR-0007/0009) для обновления уже существующего документа, новый sidecar
не создаётся. Неизвестный домен получает pending_manual_review в
config/licenses.yaml (license gate, ADR-0013) — сохранение sidecar
блокируется до ручного статуса.

Если домен относится к уже сконфигурированному источнику (SOURCES) —
документ пишется в его обычную папку data/raw/<source>/, иначе — в
псевдо-source data/raw/manual/ (ADR-0014 п.6), подхватывается обычным
ds_ingestion CLI (`python -m src.adapter.cli manual`) без изменений
ingestion-пайплайна.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

from ..license.checker import LicenseStatus, check_license
from .config import SOURCES, SourceConfig
from .crawler import SourceCrawler
from .filters import canonicalize_url

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"
MANUAL_SOURCE_NAME = "manual"


def _resolve_source(domain: str, data_root: Path) -> tuple[SourceConfig, Path]:
    """Существующий source по домену -> его обычная папка data/raw/<name>
    (ADR-0014 п.6: "если домен туда относится"); иначе псевдо-source
    `manual` в data/raw/manual/."""
    cfg = next((c for c in SOURCES.values() if c.domain == domain), None)
    if cfg is not None:
        return cfg, data_root / cfg.name
    manual_cfg = SourceConfig(name=MANUAL_SOURCE_NAME, domain=domain, seed_urls=[], keywords=[])
    return manual_cfg, data_root / MANUAL_SOURCE_NAME


async def add_manual_document(url: str, data_root: Path = DATA_ROOT) -> dict:
    """Возвращает dict со статусом:
    - 'added' — sidecar сохранён; 'doc_id', 'meta', 'source' в результате.
    - 'duplicate' — canonical_url уже есть в корпусе; 'doc_id', 'path'.
    - 'license_pending' / 'license_denied' — license gate не пропустил; 'reason'.
    - 'failed' — скачивание не удалось или контент отклонён (thin/каталог); 'reason'.
    """
    canon = canonicalize_url(url)
    domain = urlparse(canon).netloc
    cfg, out_dir = _resolve_source(domain, data_root)
    doc_id = hashlib.sha256(canon.encode()).hexdigest()[:16]

    existing = out_dir / f"{doc_id}.json"
    if existing.exists():
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
    meta = await crawler.recrawl_url(url)
    if meta is None:
        return {
            "status": "failed",
            "reason": "не удалось скачать страницу или контент отклонён (thin content/каталог-листинг)",
        }
    return {"status": "added", "doc_id": doc_id, "meta": meta, "source": cfg.name}

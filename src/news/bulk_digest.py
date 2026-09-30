"""Массовая переработка ранее загруженных статей корпуса в черновики-
пересказы (issue #422, эпик #419, подзадача C).

Источник кандидатов — sidecar .json корпуса в data/raw/<domain>/*.json
(gar_ingest/documents.py, ADR-006 п.3), НЕ news_items: это статьи основного
корпуса, у которых уже проставлен gar_document_id (опубликованы в GAR,
ingest_document). Текст переиспользуется из уже скачанного content_path —
без повторного download; генерация — тот же generate_draft(fmt='digest',
autoclassify=True), что и у digest-веток collect.py (issue #421).

Домены из config/digest_bulk.yaml (excluded_domains) исключаются полностью
(решение эпика #419: для них остаются полные тексты со ссылкой). Дедуп —
как в collect.py: news_items.source_url UNIQUE + предварительная проверка
db.source_url_exists (issue #422: "идемпотентность — повторный запуск
пропускает уже созданные").
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from ..crawler.filters import canonicalize_url
from ..gar_ingest.paths import resolve_content_path
from . import db
from .llm_draft import LlmConfig, NotRelevantError, generate_draft

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "digest_bulk.yaml"
DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"

# Только полноценные статьи (doc_type=article) — не glossary_term/glossary_abb/
# link (агрегированные справочные документы, не годятся под пересказ).
ELIGIBLE_DOC_TYPES = {"article"}


def load_excluded_domains(path: Path = CONFIG_PATH) -> set[str]:
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(d).lower() for d in (data.get("excluded_domains") or [])}


@dataclass
class BulkDigestStats:
    dry_run: bool = False
    candidates_total: int = 0  # прошли фильтр domain/doc_type/gar_document_id
    excluded_domain: int = 0
    not_published: int = 0  # doc_type=article, но нет gar_document_id
    skipped_duplicate: int = 0
    not_relevant: int = 0
    llm_failed: int = 0
    drafted: int = 0
    limited: int = 0  # кандидаты, не обработанные из-за limit в этом прогоне
    titles: list[str] = field(default_factory=list)  # заголовки обработанных/кандидатов — для отчёта UI
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "candidates_total": self.candidates_total,
            "excluded_domain": self.excluded_domain,
            "not_published": self.not_published,
            "skipped_duplicate": self.skipped_duplicate,
            "not_relevant": self.not_relevant,
            "llm_failed": self.llm_failed,
            "drafted": self.drafted,
            "limited": self.limited,
        }


def iter_corpus_json(data_root: Path) -> list[Path]:
    """Sidecar .json корпуса — по одному уровню поддиректорий-доменов ниже
    data_root (см. build_metadata/ingest_document)."""
    if not data_root.exists():
        return []
    return sorted(data_root.glob("*/*.json"))


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("не удалось прочитать %s: %s", p, exc)
        return None


def bulk_digest(
    data_root: Path = DEFAULT_DATA_ROOT,
    db_path: Path = db.DB_PATH,
    llm_config: LlmConfig | None = None,
    excluded_domains: set[str] | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> BulkDigestStats:
    """Один прогон массовой переработки.

    dry_run=True — только считает кандидатов (после фильтра
    домен/doc_type/gar_document_id/дедуп), не вызывает LLM и не пишет
    news_items (issue #422: "dry-run с подсчётом").
    limit — максимум статей, реально отправленных в LLM за этот прогон
    (не считая dry_run); остальные кандидаты остаются нетронутыми для
    следующего прогона (issue #422: "лимит и прогресс").
    progress_cb(processed, title) вызывается перед каждым LLM-вызовом —
    для прогресс-бара UI/CLI.
    """
    db.init_db(db_path)
    excluded = {d.lower() for d in (excluded_domains if excluded_domains is not None else load_excluded_domains())}
    stats = BulkDigestStats(dry_run=dry_run)
    processed = 0

    for p in iter_corpus_json(data_root):
        item = _load(p)
        if item is None:
            continue
        if item.get("doc_type") not in ELIGIBLE_DOC_TYPES:
            continue
        if not item.get("gar_document_id"):
            stats.not_published += 1
            continue
        domain = (item.get("source_domain") or "").lower()
        if domain in excluded:
            stats.excluded_domain += 1
            continue

        source_url = item.get("source_url")
        if not source_url:
            continue
        canon = canonicalize_url(source_url)
        if db.source_url_exists(canon, db_path):
            stats.skipped_duplicate += 1
            continue

        stats.candidates_total += 1
        title = item.get("title") or source_url

        if dry_run:
            stats.titles.append(title)
            continue
        if limit is not None and processed >= limit:
            stats.limited += 1
            continue

        content_path = resolve_content_path(p, item.get("content_path"))
        if not content_path.exists():
            stats.errors.append(f"{p}: content_path не найден: {content_path}")
            continue

        processed += 1
        if progress_cb:
            progress_cb(processed, title)

        llm_source = {
            "source_url": source_url,
            "source_name": domain,
            "source_published_at": None,
            "title": item.get("title"),
            "text": content_path.read_text(encoding="utf-8"),
        }
        try:
            draft = generate_draft(llm_source, config=llm_config, fmt="digest", autoclassify=True)
        except NotRelevantError as exc:
            logger.info("%s пропущен (нерелевантно): %s", source_url, exc)
            stats.not_relevant += 1
            continue
        except Exception as exc:  # noqa: BLE001 — ошибка одной статьи не должна ронять весь прогон
            logger.warning("generate_draft упал для %s: %s", source_url, exc)
            stats.llm_failed += 1
            stats.errors.append(f"{source_url}: {exc}")
            continue

        try:
            db.insert_news_item(draft, db_path)
        except Exception as exc:  # noqa: BLE001 — гонка дедупа/иное; не ронять прогон
            logger.info("news_item для %s не вставлен: %s", source_url, exc)
            stats.skipped_duplicate += 1
            continue
        stats.drafted += 1
        stats.titles.append(title)

    logger.info("bulk digest: %s", stats.as_dict())
    return stats

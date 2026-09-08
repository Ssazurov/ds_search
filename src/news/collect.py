"""Cron-пайплайн автосбора новостей: SearchChain -> dedup -> download ->
LLM-draft -> news_items status=draft (issue #61, ADR-003, эпик #44).

Намеренно НЕ использует discovery.run_search/gar_client (discovered_sources
в GAR) — та очередь предназначена для ручной курации основного корпуса
(ADR-002) и имеет свой смысл "review before download". News-пайплайн
работает автономно (без approve) и дедуплицируется по своей таблице
news_items (UNIQUE source_url, issue #47) — смешивать очереди значило бы
путать кураторов основного корпуса находками новостного крон-джоба.

Переиспользует discovery.download.download_single для получения полного
текста источника: та же crawl4ai-конфигурация (fit_markdown/PDF-тизер) и,
что важно, тот же license-гейт (check_license) — домен, не прошедший
ручную проверку ToS в config/licenses.yaml, автосбором новостей не
скачивается (issue #3, ADR-001 п.3), это тот же safety-барьер, что и для
основного корпуса.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from ..crawler.filters import canonicalize_url
from ..discovery.download import DEFAULT_DATA_ROOT, DownloadError, download_single
from ..search.base import QuotaExceeded, SearchHit
from ..search.chain import SearchProviderChain
from . import db
from .llm_draft import LlmConfig, generate_draft

logger = logging.getLogger(__name__)

QUERIES_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "news_search_queries.yaml"


@dataclass
class CollectStats:
    queries_run: int = 0
    queries_failed: int = 0
    candidates_found: int = 0
    skipped_duplicate: int = 0
    skipped_license: int = 0
    download_failed: int = 0
    llm_failed: int = 0
    drafted: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "queries_run": self.queries_run,
            "queries_failed": self.queries_failed,
            "candidates_found": self.candidates_found,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_license": self.skipped_license,
            "download_failed": self.download_failed,
            "llm_failed": self.llm_failed,
            "drafted": self.drafted,
        }


def load_queries_config(path: Path = QUERIES_CONFIG_PATH) -> tuple[list[dict], int]:
    """Возвращает (queries, max_results_per_query) из
    config/news_search_queries.yaml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    queries = data.get("queries") or []
    max_results = int(data.get("max_results_per_query", 5))
    return queries, max_results


async def _collect_one(
    hit: SearchHit, llm_config: LlmConfig | None, data_root: Path, db_path: Path,
) -> str:
    """Скачивает источник и создаёт LLM-черновик. Возвращает статус для
    статистики: 'drafted' | 'license_denied' | 'download_failed' |
    'llm_failed'. Бросает исключение только при непредвиденных ошибках —
    вызывающий код всё равно перехватывает per-item (issue #61: "ошибка
    одного источника не должна ронять весь прогон")."""
    domain = urlsplit(hit.url).netloc.lower()
    source = {"url": hit.url, "domain": domain, "title": hit.title}

    try:
        meta = await download_single(source, data_root=data_root)
    except DownloadError as exc:
        if "license status" in str(exc):
            logger.info("источник %s пропущен (лицензия): %s", hit.url, exc)
            return "license_denied"
        logger.warning("download_single не смог скачать %s: %s", hit.url, exc)
        return "download_failed"

    content_path = Path(meta["content_path"])
    if content_path.suffix == ".pdf":
        # PDF-тизер без текста — LLM-драфту нечего суммаризировать здесь;
        # такие источники остаются кандидатом для ручной курации (ADR-002),
        # не для автоновости.
        logger.info("источник %s — PDF-тизер, пропущен для новостей", hit.url)
        return "download_failed"

    text = content_path.read_text(encoding="utf-8")
    llm_source = {
        "source_url": meta["source_url"],
        "source_name": domain,
        "source_published_at": None,
        "title": meta.get("title") or hit.title,
        "text": text,
    }
    try:
        draft = generate_draft(llm_source, config=llm_config)
    except Exception as exc:  # noqa: BLE001 — любая ошибка LLM/парсинга JSON не должна ронять прогон
        logger.warning("generate_draft упал для %s: %s", hit.url, exc)
        return "llm_failed"

    try:
        db.insert_news_item(draft, db_path)
    except Exception as exc:  # noqa: BLE001 — гонка дедупа (source_url_exists прошёл, но UNIQUE сработал)
        logger.info("news_item для %s не вставлен (дубликат?): %s", hit.url, exc)
        return "skipped_duplicate"
    return "drafted"


async def collect_news(
    chain: SearchProviderChain,
    queries: list[dict] | None = None,
    max_results: int | None = None,
    llm_config: LlmConfig | None = None,
    data_root: Path = DEFAULT_DATA_ROOT,
    db_path: Path = db.DB_PATH,
) -> CollectStats:
    """Один прогон cron-пайплайна. queries/max_results — если не заданы,
    берутся из config/news_search_queries.yaml."""
    if queries is None or max_results is None:
        cfg_queries, cfg_max_results = load_queries_config()
        queries = queries if queries is not None else cfg_queries
        max_results = max_results if max_results is not None else cfg_max_results

    db.init_db(db_path)
    stats = CollectStats()

    for q in queries:
        query = q["query"] if isinstance(q, dict) else q
        try:
            hits = chain.search(query, max_results=max_results)
        except QuotaExceeded as exc:
            logger.warning("поиск по %r не выполнен (квота): %s", query, exc)
            stats.queries_failed += 1
            stats.errors.append(f"query={query!r}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 — один сбойный запрос не должен ронять весь прогон
            logger.warning("поиск по %r упал: %s", query, exc)
            stats.queries_failed += 1
            stats.errors.append(f"query={query!r}: {exc}")
            continue

        stats.queries_run += 1
        for hit in hits:
            canon = canonicalize_url(hit.url)
            stats.candidates_found += 1
            if db.source_url_exists(canon, db_path):
                stats.skipped_duplicate += 1
                continue
            try:
                result = await _collect_one(hit, llm_config, data_root, db_path)
            except Exception as exc:  # noqa: BLE001 — непредвиденная ошибка одного источника не должна ронять прогон
                logger.exception("необработанная ошибка на источнике %s", hit.url)
                stats.errors.append(f"url={hit.url}: {exc}")
                continue
            if result == "drafted":
                stats.drafted += 1
            elif result == "license_denied":
                stats.skipped_license += 1
            elif result == "download_failed":
                stats.download_failed += 1
            elif result == "llm_failed":
                stats.llm_failed += 1
            elif result == "skipped_duplicate":
                stats.skipped_duplicate += 1

    logger.info("news collect: %s", stats.as_dict())
    return stats

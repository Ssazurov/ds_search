"""Полное скачивание одной одобренной находки (issue #20 п.1, ADR-002 п.4-5,
"Уточнения 2026-09-07").

НЕ переиспользует SourceCrawler.run() — тот делает BestFirstCrawlingStrategy
обход всего домена (issue #2), здесь нужен один AsyncWebCrawler.arun(url)
без deep-crawl, "шаг после approve", не автономный обход сайта. PDF-тизер/
save-логика (issue #8/#11) переиспользована в компактном виде.

local_path не хранится в discovered_sources — вычисляется по конвенции
doc_id = sha256(canonicalize_url(url))[:16], data/raw/<domain>/<doc_id>.json,
той же, что использует SourceCrawler._save/_download_pdf (см. find_local_document).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from ..crawler.filters import (
    AdaptiveMarkdownGenerator,
    build_content_filter,
    canonicalize_url,
    find_pdf_teaser_link,
    is_pdf_teaser_page,
)
from ..license.checker import check_license
from ..metadata.profile import build_ingestion_metadata

logger = logging.getLogger(__name__)

MIN_FIT_MARKDOWN_CHARS = 200
DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


class DownloadError(RuntimeError):
    """Скачивание не удалось — вызывающая сторона переводит источник в error."""


def doc_id_for(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode()).hexdigest()[:16]


def _sanitize_filename(name: str) -> str:
    """issue #67: пользовательское имя файла -> безопасный basename без
    расширения (расширение .md/.json/.pdf дописывается вызывающей стороной),
    без разделителей пути и без выхода за пределы out_dir."""
    stem = Path(name.strip()).stem or name.strip()
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in stem)
    safe = safe.strip("_.") or "document"
    return safe[:100]


def find_local_document(domain: str, url: str, data_root: Path = DEFAULT_DATA_ROOT) -> dict | None:
    """Уже скачанный документ для этого URL, если есть (issue #20 —
    "ссылка на итоговый локальный путь" вычисляется, а не хранится в БД)."""
    json_path = data_root / domain / f"{doc_id_for(url)}.json"
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


async def _save_pdf(pdf_url: str, teaser_url: str, domain: str, direction: str,
                     license_result, out_dir: Path, base_name: str | None = None,
                     category: str | None = None, lifecycle_stage: str | None = None) -> dict | None:
    pdf_url = urljoin(teaser_url, pdf_url)
    doc_id = base_name or doc_id_for(teaser_url)
    pdf_path = out_dir / f"{doc_id}.pdf"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()
            pdf_path.write_bytes(resp.content)
    except httpx.HTTPError as exc:
        logger.warning("не удалось скачать PDF %s: %s", pdf_url, exc)
        return None

    meta = build_ingestion_metadata(
        source_url=teaser_url, source_domain=domain, title="",
        license=license_result.status.value, category=category,
        lifecycle_stage=lifecycle_stage, pdf_url=pdf_url, direction=direction,
        attribution=license_result.build_attribution(title="", source_url=teaser_url),
        content_path=str(pdf_path), content_status="saved",
    )
    (out_dir / f"{doc_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


async def download_single(
    source: dict,
    data_root: Path = DEFAULT_DATA_ROOT,
    dest_dir: Path | str | None = None,
    filename: str | None = None,
) -> dict:
    """source — discovered_source dict (url, domain, suggested_direction, ...).
    dest_dir (issue #67, ручная закачка одной страницы) — переопределяет
    data_root/domain как папку сохранения; relative разрешается от
    data_root, absolute используется как есть.
    filename — переопределяет doc_id-based базовое имя (.md/.json/.pdf
    дописываются автоматически); санитизируется до безопасного basename.
    Возвращает meta doc (content_path/content_status) либо кидает DownloadError."""
    url = source["url"]
    domain = source.get("domain") or urlsplit(url).netloc
    direction = source.get("suggested_direction") or "methodology"
    category = source.get("suggested_category") or source.get("category")
    lifecycle_stage = source.get("lifecycle_stage") or source.get("suggested_lifecycle_stage")

    license_result = check_license(domain, url)
    if not license_result.downloadable:
        raise DownloadError(f"license status {license_result.status.value}: {license_result.reason}")

    data_root_resolved = Path(data_root).resolve()
    if dest_dir is not None:
        dest_dir = Path(dest_dir)
        if dest_dir.is_absolute():
            raise DownloadError("папка назначения должна быть относительной data_root")
        out_dir = (data_root_resolved / dest_dir).resolve()
        if out_dir != data_root_resolved and data_root_resolved not in out_dir.parents:
            raise DownloadError("папка назначения не может выходить за пределы data_root")
    else:
        out_dir = data_root_resolved / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    canon = canonicalize_url(url)
    base_name = _sanitize_filename(filename) if filename else None

    run_cfg = CrawlerRunConfig(markdown_generator=AdaptiveMarkdownGenerator(content_filter=build_content_filter()))
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        result = result[0] if isinstance(result, list) else result
        if not result.success:
            raise DownloadError(f"fetch failed: {getattr(result, 'error_message', 'unknown')}")

        html = result.html or ""
        if is_pdf_teaser_page(html):
            pdf_url = find_pdf_teaser_link(html)
            if pdf_url:
                meta = await _save_pdf(pdf_url, canon, domain, direction, license_result, out_dir, base_name, category, lifecycle_stage)
                if meta:
                    return meta
            raise DownloadError("PDF-тизер без доступной прямой ссылки")

        fit_md = getattr(result.markdown, "fit_markdown", None) or result.markdown or ""
        fit_md = fit_md if isinstance(fit_md, str) else str(fit_md)
        if len(fit_md.strip()) < MIN_FIT_MARKDOWN_CHARS:
            pdf_url = find_pdf_teaser_link(html)
            if pdf_url:
                meta = await _save_pdf(pdf_url, canon, domain, direction, license_result, out_dir, base_name, category, lifecycle_stage)
                if meta:
                    return meta
            raise DownloadError("контент слишком короткий (thin content/SPA)")

        doc_id = base_name or doc_id_for(canon)
        md_path = out_dir / f"{doc_id}.md"
        md_path.write_text(fit_md, encoding="utf-8")
        title = (result.metadata or {}).get("title", source.get("title", ""))
        meta = build_ingestion_metadata(
            source_url=canon, source_domain=domain, title=title,
            license=license_result.status.value, category=category,
            lifecycle_stage=lifecycle_stage, direction=direction,
            attribution=license_result.build_attribution(title=title, source_url=canon),
            content_path=str(md_path), content_status="saved",
        )
        (out_dir / f"{doc_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return meta

"""Краулер источника через Crawl4AI (issue #2, #8, ADR-001).

Релевантность страниц оценивается BestFirstCrawlingStrategy +
KeywordRelevanceScorer (см. filters.py) — обходятся сначала наиболее похожие
на ключевые слова направления страницы, нерелевантные (по домену/типу/URL-
паттерну, включая RU-слаги и пагинацию — issue #8 п.1-2) отсекаются
FilterChain до скачивания.

Перед сохранением (issue #8 п.4) применяется hard-cutoff порог релевантности
по длине PruningContentFilter.fit_markdown — короткий/пустой fit_markdown
(листинг, JS-виджет без серверного рендера) не сохраняется.

Страницы-тизеры к PDF-отчётам (issue #8 п.3) не сохраняются как документ —
извлекается прямая ссылка на PDF и кладётся в очередь на скачивание, чтобы
не терять реальный контент отчёта.

URL канонизируется (filters.canonicalize_url) до хэширования и для
дедупликации между посевными URL (issue #8, дубли "Главная страница" x3
в ручном разборе корпуса) — иначе разные представления одного URL считаются
разными документами.

Проверка лицензии/ToS (issue #3, src/license/checker.py) выполняется один раз
на источник (домен) перед стартом обхода. Если статус deny/pending_manual_review
— страницы источника не скачиваются, конфиг помечается как "требует ручного
сбора" и логируется предупреждение вместо скачивания (см. ADR-001 п.3).
"""
import asyncio
import hashlib
import json
import logging
from pathlib import Path

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from ..license.checker import LicenseCheckResult, LicenseStatus, check_license
from .config import SourceConfig
from .filters import (
    build_filter_chain,
    build_relevance_scorer,
    build_content_filter,
    canonicalize_url,
    find_pdf_teaser_link,
    is_pdf_teaser_page,
    is_listing_page,
)

import httpx
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class SourceCrawler:
    def __init__(self, cfg: SourceConfig, out_dir: Path):
        self.cfg = cfg
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._seen_urls: set[str] = set()
        self.pdf_queue: list[str] = []  # issue #8 п.3: тизеры -> прямые PDF

    def _strategy(self) -> BestFirstCrawlingStrategy:
        return BestFirstCrawlingStrategy(
            max_depth=3,
            max_pages=self.cfg.max_pages,
            filter_chain=build_filter_chain(self.cfg.domain, self.cfg.exclude_slugs),
            url_scorer=build_relevance_scorer(self.cfg.keywords),
        )

    async def run(self) -> list[dict]:
        self.license_result = check_license(self.cfg.domain, self.cfg.seed_urls[0])
        if not self.license_result.downloadable:
            logger.warning(
                "источник %s (%s) требует ручного сбора: %s",
                self.cfg.name, self.cfg.domain, self.license_result.reason,
            )
            return []

        run_cfg = CrawlerRunConfig(
            deep_crawl_strategy=self._strategy(),
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=build_content_filter(),
            ),
        )
        saved: list[dict] = []
        skipped_thin = 0
        skipped_dupe = 0
        skipped_listing = 0
        async with AsyncWebCrawler() as crawler:
            for seed in self.cfg.seed_urls:
                results = await crawler.arun(url=seed, config=run_cfg)
                results = results if isinstance(results, list) else [results]
                for r in results:
                    if not r.success:
                        continue
                    canon = canonicalize_url(r.url)
                    if canon in self._seen_urls:
                        skipped_dupe += 1
                        continue

                    # issue #11: тизер к PDF-отчёту детектируется ДО проверки
                    # длины fit_markdown — блок "Похожие материалы" (ссылки)
                    # у такой карточки легко проходит min_fit_markdown_chars,
                    # хотя реального текста статьи там нет.
                    if is_pdf_teaser_page(r.html or ""):
                        pdf_url = find_pdf_teaser_link(r.html or "")
                        if pdf_url:
                            doc = await self._download_pdf(pdf_url, canon)
                            if doc:
                                self._seen_urls.add(canon)
                                saved.append(doc)
                            else:
                                self.pdf_queue.append(pdf_url)
                        continue

                    fit_md = getattr(r.markdown, "fit_markdown", None) or r.markdown or ""
                    fit_md = fit_md if isinstance(fit_md, str) else str(fit_md)
                    if len(fit_md.strip()) < self.cfg.min_fit_markdown_chars:
                        pdf_url = find_pdf_teaser_link(r.html or "")
                        if pdf_url:
                            doc = await self._download_pdf(pdf_url, canon)
                            if doc:
                                self._seen_urls.add(canon)
                                saved.append(doc)
                            else:
                                self.pdf_queue.append(pdf_url)
                        else:
                            skipped_thin += 1
                        continue

                    # issue #6/ADR-001 п.3a: каталожные/листинговые страницы
                    # (список подкатегорий/книг/интервью + вводный абзац)
                    # проходят порог по длине fit_markdown, но не содержат
                    # связного текста статьи — отсекаются по link-to-text
                    # ratio.
                    if is_listing_page(fit_md):
                        skipped_listing += 1
                        continue

                    self._seen_urls.add(canon)
                    saved.append(self._save(r, canon, fit_md))
        logger.info(
            "saved %d documents for %s (skipped_thin=%d, skipped_listing=%d, "
            "skipped_dupe=%d, pdf_queue=%d)",
            len(saved), self.cfg.name, skipped_thin, skipped_listing,
            skipped_dupe, len(self.pdf_queue),
        )
        return saved

    async def _download_pdf(self, pdf_url: str, teaser_url: str) -> dict | None:
        """issue #11: скачивает сам PDF-отчёт прямым http-запросом (не
        browser.goto — известная проблема issue #2, Playwright трактует
        переход на файл как "Download is starting" и роняет страницу)."""
        pdf_url = urljoin(teaser_url, pdf_url)
        doc_id = hashlib.sha256(pdf_url.encode()).hexdigest()[:16]
        pdf_path = self.out_dir / f"{doc_id}.pdf"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(pdf_url)
                resp.raise_for_status()
                pdf_path.write_bytes(resp.content)
        except httpx.HTTPError as exc:
            logger.warning("не удалось скачать PDF-тизер %s: %s", pdf_url, exc)
            return None

        attribution = self.license_result.build_attribution(
            title="", source_url=teaser_url,
        )
        meta = {
            "source_url": teaser_url,
            "pdf_url": pdf_url,
            "source_domain": self.cfg.domain,
            "title": "",
            "direction": self.cfg.direction,
            "license": self.license_result.status.value,
            "attribution": attribution,
            "content_path": str(pdf_path),
        }
        (self.out_dir / f"{doc_id}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return meta

    def _save(self, result, canon_url: str, fit_markdown: str) -> dict:
        doc_id = hashlib.sha256(canon_url.encode()).hexdigest()[:16]
        md_path = self.out_dir / f"{doc_id}.md"
        md_path.write_text(fit_markdown, encoding="utf-8")

        title = (result.metadata or {}).get("title", "")
        attribution = self.license_result.build_attribution(
            title=title, source_url=result.url,
        )
        meta = {
            "source_url": canon_url,
            "source_domain": self.cfg.domain,
            "title": title,
            "direction": self.cfg.direction,
            "license": self.license_result.status.value,
            "attribution": attribution,
            "content_path": str(md_path),
        }
        (self.out_dir / f"{doc_id}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return meta


async def main():
    from .config import SOURCES
    cfg = SOURCES["downsideup"]
    out_dir = Path(__file__).resolve().parents[2] / "data" / "raw" / cfg.name
    crawler = SourceCrawler(cfg, out_dir)
    docs = await crawler.run()
    print(f"Собрано документов: {len(docs)}")
    if crawler.pdf_queue:
        print(f"PDF-тизеры в очереди на скачивание: {len(crawler.pdf_queue)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

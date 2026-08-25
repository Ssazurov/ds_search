"""Краулер источника через Crawl4AI (issue #2, ADR-001).

Релевантность страниц оценивается BestFirstCrawlingStrategy +
KeywordRelevanceScorer (см. filters.py) — обходятся сначала наиболее похожие
на ключевые слова направления страницы, нерелевантные (по домену/типу/URL-
паттерну) отсекаются FilterChain до скачивания.

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

from ..license.checker import LicenseCheckResult, LicenseStatus, check_license
from .config import SourceConfig
from .filters import build_filter_chain, build_relevance_scorer

logger = logging.getLogger(__name__)


class SourceCrawler:
    def __init__(self, cfg: SourceConfig, out_dir: Path):
        self.cfg = cfg
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _strategy(self) -> BestFirstCrawlingStrategy:
        return BestFirstCrawlingStrategy(
            max_depth=3,
            max_pages=self.cfg.max_pages,
            filter_chain=build_filter_chain(self.cfg.domain),
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

        run_cfg = CrawlerRunConfig(deep_crawl_strategy=self._strategy())
        saved: list[dict] = []
        async with AsyncWebCrawler() as crawler:
            for seed in self.cfg.seed_urls:
                results = await crawler.arun(url=seed, config=run_cfg)
                results = results if isinstance(results, list) else [results]
                for r in results:
                    if not r.success or not (r.markdown or "").strip():
                        continue
                    saved.append(self._save(r))
        logger.info("saved %d documents for %s", len(saved), self.cfg.name)
        return saved

    def _save(self, result) -> dict:
        doc_id = hashlib.sha256(result.url.encode()).hexdigest()[:16]
        md_path = self.out_dir / f"{doc_id}.md"
        md_path.write_text(result.markdown or "", encoding="utf-8")

        title = (result.metadata or {}).get("title", "")
        attribution = self.license_result.build_attribution(
            title=title, source_url=result.url,
        )
        meta = {
            "source_url": result.url,
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

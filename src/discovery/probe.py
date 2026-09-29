"""Probe-этап (issue #17, ADR-002 "Уточнения"): частичная загрузка +
уточнение relevance_score по discovered_sources до полного скачивания.

По каждой находке со статусом new делается HTTP GET с обрывом чтения по
достижении cap (без браузера — известное ограничение для SPA, см. ниже),
затем тот же content-filter, что уже используется в краулере (ADR-001
п.3a, src/crawler/filters.py), даёт fit_markdown и link-to-text ratio —
уточняет предварительный relevance_score по сниппету более сильным
сигналом на основе реального контента.

SPA-ограничение: без JS-рендеринга (обычный httpx, не Playwright) контент
может подгружаться скриптом и probe даёт пустой/бедный fit_markdown. В
этом случае relevance_score не понижается ниже сниппет-оценки и источник
не отсеивается автоматически — помечается на ручной просмотр (как
thin-content в ADR-001 п.3a), а не как ошибка.
"""
from __future__ import annotations

import logging

import httpx
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from ..crawler.filters import build_content_filter, link_to_text_ratio, LTR_THRESHOLD
from ..metadata.meta_extract import extract_meta_tags, extract_page_meta
from ..search.dates import parse_published
from .config import Settings, load_settings
from .gar_client import GarDiscoveryClient

logger = logging.getLogger(__name__)

# issue #6: тот же порог, что и в краулере — контент короче не даёт
# сигнала сильнее сниппета.
MIN_FIT_MARKDOWN_CHARS = 200


async def _fetch_capped(url: str, max_bytes: int, timeout_s: float) -> str | None:
    """Потоковый GET с обрывом чтения по достижении max_bytes (issue #17:
    "без полноценного рендеринга браузером"). Возвращает None при сетевой
    ошибке — probe не блокирует пайплайн, просто не даёт уточнения."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_s) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= max_bytes:
                        break
                raw = b"".join(chunks)
                return raw.decode(resp.encoding or "utf-8", errors="replace")
    except httpx.HTTPError as exc:
        logger.warning("probe fetch failed for %s: %s", url, exc)
        return None


def _score_from_content(fit_markdown: str) -> float | None:
    """Возвращает уточнённый score 0..1 по объёму полезного текста и LTR,
    либо None если контента недостаточно для сигнала сильнее сниппета
    (короткий/пустой fit_markdown — thin content или SPA, ADR-002)."""
    text = (fit_markdown or "").strip()
    if len(text) < MIN_FIT_MARKDOWN_CHARS:
        return None
    ltr = link_to_text_ratio(text)
    if ltr > LTR_THRESHOLD:
        return 0.1  # каталог/листинг — низкая релевантность, не отсев
    # длина как прокси "содержательности", с насыщением на ~3000 симв.
    length_component = min(len(text) / 3000, 1.0)
    ltr_component = 1.0 - (ltr / LTR_THRESHOLD)
    return round(0.5 * length_component + 0.5 * ltr_component, 3)


async def probe_source(url: str, settings: Settings) -> dict:
    """Выполняет probe одного URL. Возвращает dict с ключами
    relevance_score (float|None) и probe_status ('scored'|'thin'|'error')
    для логирования/диагностики вызывающей стороной."""
    html = await _fetch_capped(url, settings.probe_max_bytes, settings.probe_timeout_s)
    if html is None:
        return {"relevance_score": None, "probe_status": "error", "source_published_at": None}

    # #355: дата публикации из og/article meta-тегов (fallback к дате провайдера)
    published = parse_published(extract_page_meta(extract_meta_tags(html))["publish_date"])

    generator = DefaultMarkdownGenerator()
    result = generator.generate_markdown(input_html=html, base_url=url, content_filter=build_content_filter())
    fit_markdown = result.fit_markdown or ""

    score = _score_from_content(fit_markdown)
    if score is None:
        return {"relevance_score": None, "probe_status": "thin", "source_published_at": published}
    return {"relevance_score": score, "probe_status": "scored", "source_published_at": published}


async def run_probe_stage(
    status: str = "new",
    settings: Settings | None = None,
    only_missing_date: bool = False,
) -> dict:
    """Прогоняет probe по всем discovered_sources с заданным статусом
    (issue #17). Обновляет relevance_score через PATCH
    /discovered-sources/{id}; статус находки не меняется — probe только
    уточняет оценку, решение approve/reject остаётся за пользователем.
    
    При only_missing_date=True (issue #360, backfill режим):
    - пропускаются находки, у которых source_published_at уже заполнена
    - relevance_score не обновляется (режим "только дата")
    - пауза 0.5с между запросами для снижения нагрузки на сайты
    
    Возвращает счётчики для лога: scored/thin/error/skipped/updated."""
    import asyncio
    
    settings = settings or load_settings()
    counts = {"scored": 0, "thin": 0, "error": 0, "skipped": 0, "updated": 0}
    with GarDiscoveryClient(settings) as client:
        sources = client.list_discovered_sources(status=status)
        for src in sources:
            # backfill: пропускаем, если дата уже есть
            if only_missing_date and src.get("source_published_at"):
                counts["skipped"] += 1
                continue
                
            outcome = await probe_source(src["url"], settings)
            counts[outcome["probe_status"]] += 1
            fields = {}
            
            # в backfill режиме не трогаем relevance_score
            if not only_missing_date and outcome["relevance_score"] is not None:
                fields["relevance_score"] = outcome["relevance_score"]
            
            # #355: дату источника не перезаписываем — только заполняем пустую
            published = outcome.get("source_published_at")
            if published and not src.get("source_published_at"):
                fields["source_published_at"] = published.isoformat()
                
            if fields:
                client.update_discovered_source(src["id"], **fields)
                counts["updated"] += 1
                
            logger.info("probe %s: %s (%s)", src["url"], outcome["probe_status"], outcome["relevance_score"])
            
            # backfill: пауза между запросами
            if only_missing_date:
                await asyncio.sleep(0.5)
                
    logger.info("probe stage done: %s", counts)
    return counts


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Probe discovered sources для уточнения relevance_score и даты публикации")
    parser.add_argument("--only-missing-date", action="store_true", 
                        help="Backfill режим: обновлять только дату у записей без source_published_at, не трогать relevance_score")
    parser.add_argument("--status", default="new", 
                        help="Статус находок для обработки (по умолчанию: new)")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logger.info("Запуск probe: status=%s, only_missing_date=%s", args.status, args.only_missing_date)
    counts = await run_probe_stage(status=args.status, only_missing_date=args.only_missing_date)
    
    print(f"\nProbe завершён:")
    print(f"  Обработано: {counts['scored']} scored, {counts['thin']} thin, {counts['error']} error")
    print(f"  Пропущено (дата есть): {counts['skipped']}")
    print(f"  Обновлено в БД: {counts['updated']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

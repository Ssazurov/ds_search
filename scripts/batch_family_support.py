"""Разовый батч-скрипт: скачать все находки family_support с листинга
downsideup.org (ручная задача Paul, 2026-09-10). Переиспользует
discovery.download.download_single - та же лицензионная/фильтрующая логика,
что и в остальном пайплайне."""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.discovery.download import download_single, DownloadError

LIST_BASE = (
    "https://downsideup.org/elektronnaya-biblioteka/filter/age_start-from-0/"
    "age_end-to-100/tags-is-rasskazy-roditeley/apply/"
)
HEADERS = {"User-Agent": "Mozilla/5.0"}
LINK_RE = re.compile(r'/elektronnaya-biblioteka/([a-z0-9\-]+)/')
DOMAIN = "downsideup.org"
DEST_DIR = "family_support"


async def collect_slugs() -> list[str]:
    """Собрать все слаги со всех страниц листинга (пагинация PAGEN_1)."""
    import httpx as _httpx

    slugs: set[str] = set()
    page = 1
    async with _httpx.AsyncClient(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        while True:
            url = LIST_BASE if page == 1 else LIST_BASE + f"?PAGEN_1={page}"
            resp = await client.get(url)
            # Bitrix SEF на этом фильтре отдаёт 200-контент с HTTP 404 —
            # статус игнорируем, ориентируемся на наличие новых ссылок.
            found = set(LINK_RE.findall(resp.text)) - {"filter"}
            new = found - slugs
            if not new:
                break
            slugs |= new
            page += 1
            if page > 30:
                break
    return sorted(slugs)


async def main():
    slugs = await collect_slugs()
    print(f"найдено ссылок: {len(slugs)}")
    ok, skip, err = 0, 0, 0
    for slug in slugs:
        url = f"https://downsideup.org/elektronnaya-biblioteka/{slug}/"
        source = {
            "url": url,
            "domain": DOMAIN,
            "suggested_direction": "family_support",
            "suggested_category": "family_support",
        }
        try:
            meta = await download_single(source, dest_dir=DEST_DIR, filename=slug)
            print(f"OK   {slug} -> {meta['content_path']}")
            ok += 1
        except DownloadError as exc:
            print(f"SKIP {slug}: {exc}")
            skip += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERR  {slug}: {exc}")
            err += 1
    print(f"итого: ok={ok} skip={skip} err={err} total={len(slugs)}")


if __name__ == "__main__":
    asyncio.run(main())

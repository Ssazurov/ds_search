"""Разовый батч: скачать все ссылки на статьи с filter-страницы downsideup.org
(tags-is-rasskazy-roditeley) в data/raw/downsideup.org/family_support/,
используя src.discovery.download.download_single (issue #67 API).
Запуск: python scripts/batch_download_family_support.py
"""
import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.discovery.download import DownloadError, download_single  # noqa: E402

BASE = "https://downsideup.org"
LIST_URL = (
    "https://downsideup.org/elektronnaya-biblioteka/filter/age_start-from-0/"
    "age_end-to-100/tags-is-rasskazy-roditeley/apply/"
    "?SMART_FILTER_PATH=age_start-from-0%2Fage_end-to-100%2Ftags-is-rasskazy-roditeley%2Fapply&SIZEN_1=36"
)
ARTICLE_RE = re.compile(r'href="(/elektronnaya-biblioteka/[a-z0-9\-]+/)"')


async def collect_links() -> list[str]:
    links: set[str] = set()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        page = 1
        url = LIST_URL
        while True:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            found = {urljoin(BASE, m) for m in ARTICLE_RE.findall(resp.text)}
            if not found - links:
                break
            links |= found
            page += 1
            if page > 20:
                break
            sep = "&" if "?" in LIST_URL else "?"
            url = f"{LIST_URL}{sep}PAGEN_1={page}"
    return sorted(links)


def slug_of(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


async def main() -> None:
    links = await collect_links()
    print(f"найдено ссылок: {len(links)}")
    ok, skip, err = 0, 0, 0
    for url in links:
        slug = slug_of(url)
        source = {
            "url": url,
            "domain": "downsideup.org",
            "suggested_direction": "family_support",
            "suggested_category": "family_support",
        }
        try:
            meta = await download_single(source, dest_dir="family_support", filename=slug)
            print(f"OK   {slug} -> {meta.get('content_path')}")
            ok += 1
        except DownloadError as exc:
            print(f"ERR  {slug}: {exc}")
            err += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERR  {slug}: unexpected {exc}")
            err += 1
    print(f"\nитого: ok={ok} err={err} total={len(links)}")


if __name__ == "__main__":
    asyncio.run(main())

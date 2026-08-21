"""Step 2 of extraction: download article pages, with an on-disk cache.

The cache matters more than it looks. Re-parsing 2,300 articles to fix one
regex should not mean re-crawling Bandcamp for an hour, so every page is
written to ``data/raw/html_cache/<slug>.html`` once and read from disk on
every later run. That makes the parse step instant, idempotent and testable
offline, and it holds the crawl footprint on Bandcamp to exactly one request
per article, ever.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

import requests

from .. import config
from .http import FetchError, get

logger = logging.getLogger(__name__)


def slug_for(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def cache_path_for(url: str, cache_dir: Path | None = None) -> Path:
    cache_dir = cache_dir or config.HTML_CACHE_DIR
    return cache_dir / f"{slug_for(url)}.html"


def fetch_articles(
    session: requests.Session,
    urls: Iterable[str],
    *,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    progress_every: int = 100,
) -> Iterator[tuple[str, str]]:
    """Yield ``(url, html)`` for each URL, downloading only what isn't cached."""
    cache_dir = cache_dir or config.HTML_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    urls = list(urls)
    total = len(urls)
    downloaded = cached = failed = 0

    for i, url in enumerate(urls, start=1):
        path = cache_path_for(url, cache_dir)

        if use_cache and path.exists() and path.stat().st_size > 500:
            cached += 1
            yield url, path.read_text(encoding="utf-8")
        else:
            try:
                response = get(session, url)
            except FetchError as exc:
                logger.error("Could not fetch %s: %s", url, exc)
                failed += 1
                yield url, ""
                continue

            html = response.text if response else ""
            if len(html) > 500:
                path.write_text(html, encoding="utf-8")
                downloaded += 1
            else:
                failed += 1
            time.sleep(config.REQUEST_DELAY_SECONDS)
            yield url, html

        if progress_every and i % progress_every == 0:
            logger.info("Fetched %d/%d (%d new, %d cached, %d failed)",
                        i, total, downloaded, cached, failed)

    logger.info("Fetch complete: %d new, %d from cache, %d failed",
                downloaded, cached, failed)

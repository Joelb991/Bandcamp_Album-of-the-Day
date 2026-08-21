"""Extraction: Bandcamp Daily -> a tidy article-level DataFrame."""
from __future__ import annotations

import logging
from collections.abc import Iterable

import pandas as pd

from .discover import article_urls_on_page, discover_article_urls
from .fetch import cache_path_for, fetch_articles, slug_for
from .http import FetchError, build_session, get
from .parse import parse_article

logger = logging.getLogger(__name__)

__all__ = [
    "article_urls_on_page", "discover_article_urls",
    "fetch_articles", "cache_path_for", "slug_for",
    "build_session", "get", "FetchError",
    "parse_article", "scrape_articles",
]


def scrape_articles(
    *,
    known_urls: Iterable[str] | None = None,
    max_pages: int | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Run discover -> fetch -> parse and return one row per article.

    Pass ``known_urls`` (the article URLs already in the warehouse) to make
    this an incremental refresh instead of a full backfill.
    """
    session = build_session()
    urls = discover_article_urls(session, known_urls=known_urls, max_pages=max_pages)

    if not urls:
        logger.info("No new articles found - the warehouse is already current.")
        return pd.DataFrame()

    logger.info("Parsing %d article pages", len(urls))
    records = [parse_article(html, url)
               for url, html in fetch_articles(session, urls, use_cache=use_cache)]

    df = pd.DataFrame.from_records(records)
    ok = int((df["parse_status"] == "ok").sum())
    logger.info("Parsed %d articles (%d complete, %d with missing fields)",
                len(df), ok, len(df) - ok)
    return df

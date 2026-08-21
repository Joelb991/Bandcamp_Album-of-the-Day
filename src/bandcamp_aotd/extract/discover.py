"""Step 1 of extraction: find the URLs of every Album of the Day article.

The archive is paginated at ``/album-of-the-day?page=N``, 30 articles per
page, newest first. Because it is newest-first, an incremental refresh only
has to read from page 1 until it starts seeing URLs it already has - which is
what ``known_urls`` and ``stop_after_known`` are for. A full backfill just
omits both and walks to the end.

In practice this is the difference between a weekly refresh costing one HTTP
request and costing five hundred.
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable

import requests

from .. import config
from .http import get

logger = logging.getLogger(__name__)

# Article links look like /album-of-the-day/<slug>; the trailing character
# class stops the match at the closing quote or angle bracket.
ARTICLE_LINK_RE = re.compile(r"/album-of-the-day/[a-z][^\"' >]*")


def article_urls_on_page(html: str) -> list:
    """Return the ordered, de-duplicated article URLs found in one index page."""
    seen = {}
    for path in ARTICLE_LINK_RE.findall(html):
        seen.setdefault(f"{config.BANDCAMP_BASE_URL}{path}", None)
    return list(seen)


def discover_article_urls(
    session: requests.Session,
    *,
    known_urls: Iterable[str] | None = None,
    stop_after_known: int = 30,
    max_pages: int | None = None,
) -> list:
    """Walk the index newest-first and return article URLs not already known.

    Parameters
    ----------
    known_urls
        URLs already in the warehouse. Passing these turns a full crawl into
        an incremental one.
    stop_after_known
        Stop once this many consecutive already-known URLs have been seen -
        one full page's worth by default, which is enough to be confident the
        crawler has caught up without betting on a single article.
    max_pages
        Safety valve; defaults to ``config.MAX_INDEX_PAGES``.
    """
    known = set(known_urls or ())
    max_pages = max_pages or config.MAX_INDEX_PAGES

    new_urls = []
    consecutive_known = 0

    for page in range(1, max_pages + 1):
        url = f"{config.BANDCAMP_BASE_URL}{config.BANDCAMP_INDEX_PATH}?page={page}"
        response = get(session, url, allow_404=True)

        if response is None:
            logger.info("Reached the end of the archive at page %d", page)
            break

        page_urls = article_urls_on_page(response.text)
        if not page_urls:
            logger.info("No article links on page %d - treating as the end", page)
            break

        for article_url in page_urls:
            if article_url in known:
                consecutive_known += 1
            else:
                consecutive_known = 0
                new_urls.append(article_url)

        logger.info("Page %-3d | %2d links | %4d new so far",
                    page, len(page_urls), len(new_urls))

        if known and consecutive_known >= stop_after_known:
            logger.info("Caught up: %d consecutive known articles, stopping at page %d",
                        consecutive_known, page)
            break

        time.sleep(config.INDEX_PAGE_DELAY_SECONDS)

    # De-duplicate across pages while preserving newest-first order.
    return list(dict.fromkeys(new_urls))

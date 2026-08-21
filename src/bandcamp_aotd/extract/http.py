"""A single, polite HTTP session shared by every extract step.

Bandcamp Daily is an editorial site, not an API, so this layer does the three
things that keep a scrape from either failing or being rude:

1. Presents a real browser User-Agent and warms up cookies before paginating.
2. Retries on 429 / 5xx with exponential backoff, honouring ``Retry-After``.
3. Sleeps between requests so the crawl stays well under one request/second.
"""
from __future__ import annotations

import logging
import random
import time

import requests

from .. import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 4
MAX_WAIT_SECONDS = 120


class FetchError(RuntimeError):
    """Raised when a URL could not be retrieved after every retry."""


def build_session() -> requests.Session:
    """Return a warmed-up session with browser-like headers."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    try:
        # Warm-up request so Bandcamp sets its cookies before we paginate.
        session.get(config.BANDCAMP_BASE_URL, timeout=30)
    except requests.RequestException as exc:  # pragma: no cover - network
        logger.warning("Warm-up request failed (continuing anyway): %s", exc)
    return session


def get(
    session: requests.Session,
    url: str,
    *,
    allow_404: bool = False,
    timeout: int = 30,
) -> requests.Response | None:
    """GET ``url`` with retry and backoff.

    Returns the response, or ``None`` when the page is a 404 and ``allow_404``
    is set - which is how index pagination detects the end of the archive.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            wait = min(2 ** attempt + random.uniform(0, 0.5), MAX_WAIT_SECONDS)
            logger.warning("%s on %s - retrying in %.0fs", type(exc).__name__, url, wait)
            time.sleep(wait)
            continue

        if response.status_code == 404 and allow_404:
            return None

        if response.status_code == 429:
            wait = min(float(response.headers.get("Retry-After", 30)), MAX_WAIT_SECONDS)
            logger.warning("Rate limited on %s - waiting %.0fs (attempt %d/%d)",
                           url, wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
            continue

        if response.status_code in (500, 502, 503, 504):
            wait = min(2 ** attempt + random.uniform(0, 0.5), MAX_WAIT_SECONDS)
            logger.warning("Server error %s on %s - retrying in %.0fs",
                           response.status_code, url, wait)
            time.sleep(wait)
            continue

        if response.status_code != 200:
            raise FetchError(f"{response.status_code} on {url}")

        return response

    raise FetchError(f"Gave up on {url} after {MAX_RETRIES} attempts")

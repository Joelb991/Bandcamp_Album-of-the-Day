"""Bridge from the original CSV exports to the current schema.

The project produced three generations of CSV before it had a warehouse:

* ``data/raw/aotd_articles_2021-12.csv``   - first scrape, 1,456 articles
* ``data/processed/aotd_articles.csv``      - re-scrape, 2,288 articles
* ``data/processed/aotd_articles_enriched.csv`` - the same, plus Spotify

They all use the original ``Title_Case`` column names and none of them carry
an article URL. Rather than rename columns by hand in a notebook every time,
this module maps them onto the current snake_case schema so history flows
through exactly the same transform code as anything scraped today.

That matters for one reason: the 2016-2026 archive can be backfilled without
re-crawling 2,300 pages, and the resulting rows are indistinguishable from
freshly scraped ones once they land.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import config

logger = logging.getLogger(__name__)

# Original export column -> current schema column.
LEGACY_COLUMN_MAP = {
    "Date": "published_date",
    "Title": "title",
    "Album": "album",
    "Artist": "artist",
    "Tags": "genre_tag",
    "Record_Label": "record_label",
    "Record_Label_Loc": "label_location_raw",
    "Author": "author",
}


def load_legacy_csv(path: Path | None = None) -> pd.DataFrame:
    """Read a legacy CSV export and return it under the current column names.

    Spotify columns are already snake_case and pass through untouched.
    Columns the current schema has no home for are dropped with a log line
    rather than silently.
    """
    path = Path(path or config.ENRICHED_CSV)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Point --input at one of the CSVs in data/."
        )

    df = pd.read_csv(path)
    logger.info("Loaded %d rows x %d columns from %s", len(df), df.shape[1], path.name)

    renamed = df.rename(columns=LEGACY_COLUMN_MAP)

    if "title" not in renamed.columns and {"artist", "album"} <= set(renamed.columns):
        # The earliest export dropped the headline; rebuild it so the column
        # is populated for every generation of the data.
        renamed["title"] = renamed["artist"].fillna("") + ", " + renamed["album"].fillna("")

    unmapped = [c for c in renamed.columns
                if c not in LEGACY_COLUMN_MAP.values()
                and not c.startswith("spotify_")
                and c not in ("title", "article_url", "article_slug")]
    if unmapped:
        logger.info("Columns not part of the current schema (ignored): %s", unmapped)

    return renamed

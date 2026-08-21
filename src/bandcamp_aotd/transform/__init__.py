"""Transformation: raw scraped records -> the analytics-ready table.

``build_analytics_table`` is the one function the rest of the project calls.
Keeping the stage order in a single place means the notebook, the CLI and the
tests all transform data identically — there is no second, slightly-different
copy of the cleaning logic living in a notebook cell.
"""
from __future__ import annotations

import logging

import pandas as pd

from .dates import DATE_FEATURE_COLUMNS, add_date_features
from .identity import add_article_id, make_article_id
from .locations import (
    add_location_features,
    clean_location,
    is_country,
    normalize_country,
    split_location,
)
from .text import add_label_features, normalize_text, normalize_text_columns

logger = logging.getLogger(__name__)

__all__ = [
    "add_date_features", "DATE_FEATURE_COLUMNS",
    "add_article_id", "make_article_id",
    "add_location_features", "clean_location", "split_location",
    "is_country", "normalize_country",
    "normalize_text", "normalize_text_columns", "add_label_features",
    "build_analytics_table", "ANALYTICS_COLUMNS",
]

# The canonical column order of the analytics table. Anything not listed here
# is dropped, so a stray helper column in a notebook can never leak into the
# warehouse.
ANALYTICS_COLUMNS = [
    # Identity
    "article_id", "article_url", "article_slug",
    # Calendar
    "published_date", "year", "quarter", "month", "month_name",
    "iso_week", "day_of_month", "day_of_week_num", "day_of_week",
    # Editorial
    "author", "title", "genre_tag",
    # Release
    "artist", "album", "record_label", "is_independent",
    # Geography
    "label_location_raw", "location_clean", "city", "state", "country",
    # Spotify enrichment
    "spotify_match_status", "spotify_id", "spotify_url", "spotify_artist_id",
    "spotify_match_artist", "spotify_match_album", "spotify_release_date",
    "spotify_release_date_precision", "spotify_album_type",
    "spotify_total_tracks", "spotify_image_url", "spotify_upc", "spotify_ean",
    "spotify_copyright", "spotify_artist_status", "spotify_artist_image_url",
    "spotify_artist_url",
]


def build_analytics_table(df: pd.DataFrame) -> pd.DataFrame:
    """Run every transformation stage in order and return the modelled table.

    Stages
    ------
    1. Normalise text (entities, smart quotes, whitespace).
    2. Derive calendar attributes from the published date.
    3. Standardise locations and split them into city / state / country.
    4. Derive the independent-artist flag.
    5. Mint the deterministic ``article_id`` and de-duplicate on it.
    6. Enforce the canonical column set and order.

    Steps 1-2 run before step 5 on purpose: the id is hashed from the
    *normalised* date, artist and album, so cosmetic differences between the
    legacy export and a fresh scrape resolve to the same key.
    """
    logger.info("Transforming %d rows", len(df))

    out = normalize_text_columns(df)
    out = add_date_features(out)
    out = add_location_features(out)
    out = add_label_features(out)
    out = add_article_id(out)

    before = len(out)
    out = out.drop_duplicates(subset="article_id", keep="first")
    if len(out) < before:
        logger.info("Dropped %d duplicate articles on article_id", before - len(out))

    # The grain of the warehouse is "one published article", so a row with no
    # publication date is not a fact - it is a parse failure. Dropping it here,
    # loudly, is better than letting it fail the NOT NULL constraint at load
    # time or, worse, sit in the dashboard as a null-dated feature.
    undated = out["published_date"].isna()
    if undated.any():
        logger.warning(
            "Rejected %d row(s) with no publication date (unusable grain): %s",
            int(undated.sum()),
            out.loc[undated, ["article_id", "title", "artist"]].to_dict("records"),
        )
        out = out[~undated]

    for column in ANALYTICS_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA

    out = out[ANALYTICS_COLUMNS].sort_values("published_date").reset_index(drop=True)
    logger.info(
        "Analytics table ready: %d rows, %d countries, %d authors, %d genre tags",
        len(out), out["country"].nunique(), out["author"].nunique(),
        out["genre_tag"].nunique(),
    )
    return out

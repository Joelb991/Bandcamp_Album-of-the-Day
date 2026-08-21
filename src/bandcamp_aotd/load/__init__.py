"""Load: the analytics table -> Postgres, and CSV/Parquet fallbacks."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .. import config
from .postgres import (
    apply_sql_file,
    fetch_known_article_urls,
    load_analytics_table,
    read_analytics_table,
)

logger = logging.getLogger(__name__)

__all__ = [
    "apply_sql_file", "fetch_known_article_urls", "load_analytics_table",
    "read_analytics_table", "write_csv", "write_tableau_extract",
]


def write_csv(df: pd.DataFrame, path: Path | None = None) -> Path:
    """Write the analytics table to CSV.

    The database is the source of truth, but a committed CSV means the repo
    clones and runs with no credentials at all - which is what someone
    reviewing the project will actually do.
    """
    path = Path(path or config.ANALYTICS_CSV)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("Wrote %d rows to %s", len(df), path)
    return path


def write_tableau_extract(df: pd.DataFrame, path: Path | None = None) -> Path:
    """Write the flat file Tableau connects to when not using a live database.

    Tableau reads dates more reliably from ISO strings than from mixed
    formats, and it does not need the pipeline's lineage columns, so this is
    a deliberately narrower shape than the warehouse table.
    """
    path = Path(path or config.EXPORTS_DIR / "tableau_aotd_extract.csv")
    path.parent.mkdir(parents=True, exist_ok=True)

    extract = df.copy()
    extract["published_date"] = pd.to_datetime(
        extract["published_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    drop = [c for c in ("spotify_upc", "spotify_ean", "spotify_copyright",
                        "article_slug", "label_location_raw") if c in extract.columns]
    extract = extract.drop(columns=drop)
    extract.to_csv(path, index=False)
    logger.info("Wrote Tableau extract (%d rows, %d columns) to %s",
                len(extract), extract.shape[1], path)
    return path

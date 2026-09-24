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
    "export_views", "ANALYTICS_VIEWS",
]

# The semantic layer, as separate BI-ready tables. These exist because the
# metrics that are genuinely hard to express in a BI tool - Shannon entropy per
# author, city/genre lift against a global baseline - are already computed
# correctly in SQL. Re-deriving them with Tableau calculated fields would mean
# a second, subtly different definition of the same number.
ANALYTICS_VIEWS = {
    "vw_coverage_by_country": "coverage_by_country",
    "vw_city_genre_specialisation": "city_genre_specialisation",
    "vw_author_profile": "author_profile",
    "vw_genre_trend": "genre_trend",
    "vw_label_leaderboard": "label_leaderboard",
    "vw_pipeline_health": "pipeline_health",
}


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


def export_views(out_dir: Path | None = None, dsn: str | None = None) -> dict:
    """Write each analytics view to its own CSV for the BI layer.

    Returns ``{filename: row count}``. A view that fails to read is logged and
    skipped rather than aborting the whole export - a missing view should not
    cost you the five that worked.
    """
    from .postgres import _connect, read_sql

    out_dir = Path(out_dir or config.EXPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = {}
    connection = _connect(dsn)
    try:
        for view, filename in ANALYTICS_VIEWS.items():
            try:
                df = read_sql(f"SELECT * FROM {config.DATABASE.schema}.{view}", connection)
            except Exception as exc:  # noqa: BLE001 - one bad view is not fatal
                logger.warning("Could not export %s: %s", view, exc)
                continue
            path = out_dir / f"{filename}.csv"
            df.to_csv(path, index=False)
            written[path.name] = len(df)
            logger.info("Exported %-32s -> %-34s %5d rows", view, path.name, len(df))
    finally:
        connection.close()

    logger.info("Exported %d of %d views to %s",
                len(written), len(ANALYTICS_VIEWS), out_dir)
    return written


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

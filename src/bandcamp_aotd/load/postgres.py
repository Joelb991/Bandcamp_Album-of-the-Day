"""Load the analytics table into Postgres / Supabase.

The whole design goal here is that ``load`` can be run any number of times
over any overlapping date range and the warehouse ends up in the same state.
That is achieved with three things:

1. Dimensions are upserted first and their surrogate keys read back, so the
   fact rows always reference real ids.
2. The fact table is written with ``INSERT ... ON CONFLICT (article_id) DO
   UPDATE``, so a re-run corrects rows instead of duplicating them.
3. Rows are sent with ``execute_values`` in batches - one round trip per
   1,000 rows rather than one per row, which is the difference between a
   two-second load and a two-minute one.

Nothing here is Supabase-specific; the same code runs against any Postgres.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

import numpy as np
import pandas as pd

from .. import config

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

FACT_COLUMNS = [
    "article_id", "article_url", "article_slug", "published_date", "year",
    "quarter", "month", "month_name", "iso_week", "day_of_month",
    "day_of_week_num", "day_of_week", "author_id", "title", "genre_tag",
    "artist", "album", "label_id", "is_independent", "place_id",
    "label_location_raw", "spotify_match_status", "spotify_id", "spotify_url",
    "spotify_artist_id", "spotify_match_artist", "spotify_match_album",
    "spotify_release_date", "spotify_release_date_precision",
    "spotify_album_type", "spotify_total_tracks", "spotify_image_url",
    "spotify_upc", "spotify_ean", "spotify_copyright", "spotify_artist_status",
    "spotify_artist_image_url", "spotify_artist_url",
]


def _null_safe(value):
    """Make one pandas value safe to hand to psycopg2.

    Two conversions, both of which cause real bugs when skipped:

    1. **Missing values become SQL NULL.** psycopg2 adapts ``float('nan')`` to
       the PostgreSQL float literal ``NaN``; inserted into a TEXT column that
       becomes the four-character *string* "NaN", which then appears in the
       dashboard as a city called NaN.
    2. **numpy scalars become Python scalars.** psycopg2 has no adapter for
       ``numpy.int64`` and raises "can't adapt type". This only bites on the
       direct DataFrame path - a CSV round trip happens to launder the dtypes -
       so it is exactly the kind of bug that passes one code path and fails
       another.

    Every value handed to the driver goes through here first.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):        # arrays and other non-scalars
        pass
    if isinstance(value, np.generic):      # numpy scalar -> Python scalar
        return value.item()
    return value


def _connect(dsn: str | None = None):
    """Open a connection, with a clear message if the driver is missing."""
    try:
        import psycopg2  # noqa: F401
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "psycopg2-binary is required for the load stage. "
            "Install it with: pip install psycopg2-binary"
        ) from exc
    import psycopg2

    dsn = dsn or config.DATABASE.require_url()
    connection = psycopg2.connect(dsn)
    connection.autocommit = False
    return connection


def apply_sql_file(path, dsn: str | None = None) -> None:
    """Execute a .sql file (used to apply schema.sql and views.sql)."""
    sql = open(path, encoding="utf-8").read()
    with _connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(sql)
        connection.commit()
    logger.info("Applied %s", path)


def fetch_known_article_urls(dsn: str | None = None) -> set:
    """Return every article URL already in the warehouse.

    This is what makes the scrape incremental - the crawler stops as soon as
    it recognises what it is seeing.
    """
    try:
        with _connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT article_url FROM bandcamp.fact_article "
                "WHERE article_url IS NOT NULL"
            )
            urls = {row[0] for row in cursor.fetchall()}
        logger.info("Warehouse already holds %d article URLs", len(urls))
        return urls
    except Exception as exc:  # noqa: BLE001 - a cold database is not an error
        logger.warning("Could not read existing URLs (%s); doing a full crawl", exc)
        return set()


def _upsert_dimension(
    cursor, table: str, key_column: str, id_column: str,
    values: Iterable[tuple], extra_columns: Iterable[str] = (),
) -> dict:
    """Upsert dimension rows and return ``{natural key: surrogate id}``."""
    from psycopg2.extras import execute_values

    values = [tuple(_null_safe(v) for v in row) for row in values]
    values = [row for row in values if row[0] is not None]
    if not values:
        return {}

    columns = [key_column, *extra_columns]
    # DO UPDATE (rather than DO NOTHING) so RETURNING yields a row for every
    # key, including ones that already existed.
    updates = (", ".join(f"{c} = EXCLUDED.{c}" for c in extra_columns)
               or f"{key_column} = EXCLUDED.{key_column}")
    sql = (
        f"INSERT INTO bandcamp.{table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({key_column}) DO UPDATE SET {updates} "
        f"RETURNING {id_column}, {key_column}"
    )
    # fetch=True is essential: execute_values splits the rows into several
    # statements, and cursor.fetchall() would only ever see the LAST one -
    # silently losing the surrogate ids for every earlier batch, which shows up
    # much later as NULL foreign keys in the fact table.
    returned = execute_values(cursor, sql, values, page_size=BATCH_SIZE, fetch=True)
    return {key: surrogate_id for surrogate_id, key in returned}


def load_analytics_table(
    df: pd.DataFrame, dsn: str | None = None, *, run_stage: str = "load"
) -> dict:
    """Upsert the analytics table into Postgres. Returns a summary dict."""
    from psycopg2.extras import execute_values

    if df.empty:
        logger.info("Nothing to load.")
        return {"rows": 0, "inserted": 0, "updated": 0}

    frame = df.copy()
    connection = _connect(dsn)
    summary = {"rows": len(frame), "inserted": 0, "updated": 0}

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO bandcamp.pipeline_run (stage, status) "
                "VALUES (%s, 'running') RETURNING run_id",
                (run_stage,),
            )
            run_id = cursor.fetchone()[0]

            # -- dimensions ------------------------------------------------
            author_names = sorted(
                {str(a) for a in frame["author"] if a is not None and pd.notna(a)}
            )
            authors = _upsert_dimension(
                cursor, "dim_author", "author_name", "author_id",
                [(name,) for name in author_names],
            )

            label_rows = (
                frame[["record_label", "is_independent"]]
                .dropna(subset=["record_label"])
                .drop_duplicates(subset="record_label")
            )
            labels = _upsert_dimension(
                cursor, "dim_label", "label_name", "label_id",
                [(r.record_label, bool(r.is_independent)) for r in label_rows.itertuples()],
                extra_columns=["is_independent"],
            )

            place_rows = (
                frame[["location_clean", "city", "state", "country"]]
                .dropna(subset=["location_clean"])
                .drop_duplicates(subset="location_clean")
            )
            places = _upsert_dimension(
                cursor, "dim_place", "location_clean", "place_id",
                [(r.location_clean, r.city, r.state, r.country) for r in place_rows.itertuples()],
                extra_columns=["city", "state", "country"],
            )
            logger.info("Dimensions: %d authors, %d labels, %d places",
                        len(authors), len(labels), len(places))

            # -- fact ------------------------------------------------------
            fact = frame.copy()
            fact["author_id"] = fact["author"].map(authors)
            fact["label_id"] = fact["record_label"].map(labels)
            fact["place_id"] = fact["location_clean"].map(places)

            for column in FACT_COLUMNS:
                if column not in fact.columns:
                    fact[column] = None

            records = [
                tuple(_null_safe(v) for v in row)
                for row in fact[FACT_COLUMNS].itertuples(index=False, name=None)
            ]

            updatable = [c for c in FACT_COLUMNS if c != "article_id"]
            sql = (
                f"INSERT INTO bandcamp.fact_article ({', '.join(FACT_COLUMNS)}) VALUES %s "
                f"ON CONFLICT (article_id) DO UPDATE SET "
                + ", ".join(f"{c} = EXCLUDED.{c}" for c in updatable)
                + " RETURNING (xmax = 0) AS inserted"
            )
            # fetch=True for the same reason as the dimensions above - without
            # it the inserted/updated counts only describe the final batch.
            returned = execute_values(cursor, sql, records, page_size=BATCH_SIZE, fetch=True)
            flags = [row[0] for row in returned]
            summary["inserted"] = sum(flags)
            summary["updated"] = len(flags) - summary["inserted"]

            cursor.execute(
                "UPDATE bandcamp.pipeline_run SET finished_at = now(), status = 'success', "
                "rows_scraped = %s, rows_inserted = %s, rows_updated = %s WHERE run_id = %s",
                (summary["rows"], summary["inserted"], summary["updated"], run_id),
            )
        connection.commit()
        logger.info("Load complete: %d inserted, %d updated",
                    summary["inserted"], summary["updated"])
    except Exception as exc:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO bandcamp.pipeline_run (stage, status, finished_at, message) "
                "VALUES (%s, 'failed', now(), %s)",
                (run_stage, str(exc)[:500]),
            )
        connection.commit()
        raise
    finally:
        connection.close()

    return summary


def read_sql(sql: str, connection) -> pd.DataFrame:
    """Run a query on an open connection and return a DataFrame.

    Deliberately not ``pd.read_sql``: pandas routes raw DBAPI connections
    through a compatibility path that emits a UserWarning on every call and
    nudges you toward SQLAlchemy. A cursor plus ``cursor.description`` gives
    the same result, silently, with one less runtime dependency.
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        columns = [column.name for column in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columns)


def read_analytics_table(dsn: str | None = None) -> pd.DataFrame:
    """Read ``vw_article`` back out - what the analysis notebooks call."""
    connection = _connect(dsn)
    try:
        return read_sql(f"SELECT * FROM {config.DATABASE.schema}.vw_article", connection)
    finally:
        connection.close()

"""Command line entry point - the pipeline's public interface.

    python -m bandcamp_aotd init-db          # apply schema.sql + views.sql
    python -m bandcamp_aotd backfill         # load the historic CSV
    python -m bandcamp_aotd scrape           # crawl new articles -> interim CSV
    python -m bandcamp_aotd enrich           # attach Spotify metadata
    python -m bandcamp_aotd transform        # build the analytics table
    python -m bandcamp_aotd load             # upsert into Postgres
    python -m bandcamp_aotd export           # write the Tableau extract
    python -m bandcamp_aotd refresh          # scrape -> enrich -> transform -> load

``refresh`` is the one a scheduler calls. Every stage is also runnable alone,
because when something breaks at 6am you want to re-run one step, not all of
them.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from . import config
from .logging_config import setup_logging

logger = logging.getLogger("bandcamp_aotd")

INTERIM_SCRAPE = config.INTERIM_DIR / "scraped_articles.csv"
INTERIM_ENRICHED = config.INTERIM_DIR / "scraped_articles_enriched.csv"


# ── stages ──────────────────────────────────────────────────────────────────

def cmd_init_db(args) -> int:
    from .load import apply_sql_file

    apply_sql_file(config.DB_DIR / "schema.sql")
    apply_sql_file(config.DB_DIR / "views.sql")
    logger.info("Database ready.")
    return 0


def cmd_scrape(args) -> int:
    from .extract import scrape_articles
    from .load import fetch_known_article_urls

    known = set()
    if not args.full:
        known = fetch_known_article_urls() if config.DATABASE.configured else set()
        if not known:
            logger.info("No known URLs available - this run will be a full crawl.")

    df = scrape_articles(known_urls=known, max_pages=args.max_pages,
                         use_cache=not args.no_cache)
    if df.empty:
        logger.info("Nothing new to scrape.")
        return 0

    config.ensure_directories()
    df.to_csv(INTERIM_SCRAPE, index=False)
    logger.info("Wrote %d scraped articles to %s", len(df), INTERIM_SCRAPE)
    return 0


def cmd_enrich(args) -> int:
    from .enrich.spotify import SpotifyClient

    source = Path(args.input) if args.input else INTERIM_SCRAPE
    if not source.exists():
        logger.error("%s not found - run `scrape` first or pass --input.", source)
        return 1
    if not config.SPOTIFY.configured:
        logger.error("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET are not set. "
                     "Copy .env.example to .env and fill them in.")
        return 1

    df = pd.read_csv(source)
    client = SpotifyClient()

    albums = client.enrich_dataframe(
        df, artist_col="artist", album_col="album",
        checkpoint_path=str(config.SPOTIFY_ALBUM_CHECKPOINT),
    )
    enriched = pd.concat(
        [df.reset_index(drop=True), albums.reset_index(drop=True)], axis=1
    )

    artists = client.enrich_artists(
        enriched["spotify_artist_id"],
        checkpoint_path=str(config.SPOTIFY_ARTIST_CHECKPOINT),
    )
    enriched = enriched.merge(
        artists, left_on="spotify_artist_id", right_index=True, how="left"
    )

    config.ensure_directories()
    enriched.to_csv(INTERIM_ENRICHED, index=False)
    logger.info("Wrote %d enriched rows to %s", len(enriched), INTERIM_ENRICHED)
    logger.info("Spotify match rate: %.1f%%",
                100 * enriched["spotify_match_status"].eq("matched").mean())
    return 0


def cmd_transform(args) -> int:
    from .load import write_csv
    from .transform import build_analytics_table

    source = Path(args.input) if args.input else (
        INTERIM_ENRICHED if INTERIM_ENRICHED.exists() else INTERIM_SCRAPE
    )
    if not source.exists():
        logger.error("%s not found - run `scrape` first or pass --input.", source)
        return 1

    df = pd.read_csv(source)
    analytics = build_analytics_table(df)
    write_csv(analytics, args.output)
    return 0


def cmd_load(args) -> int:
    from .load import load_analytics_table

    source = Path(args.input or config.ANALYTICS_CSV)
    if not source.exists():
        logger.error("%s not found - run `transform` first.", source)
        return 1

    summary = load_analytics_table(pd.read_csv(source))
    logger.info("Loaded: %s", summary)
    return 0


def cmd_backfill(args) -> int:
    """Load the historic CSV export straight into the warehouse."""
    from .legacy import load_legacy_csv
    from .load import load_analytics_table, write_csv
    from .transform import build_analytics_table

    df = load_legacy_csv(args.input)
    analytics = build_analytics_table(df)
    write_csv(analytics)

    if args.dry_run:
        logger.info("Dry run - %d rows prepared, nothing written to the database.",
                    len(analytics))
        return 0
    logger.info("Loaded: %s", load_analytics_table(analytics, run_stage="backfill"))
    return 0


def cmd_export(args) -> int:
    from .load import read_analytics_table, write_tableau_extract

    if args.from_db:
        df = read_analytics_table()
    else:
        source = Path(args.input or config.ANALYTICS_CSV)
        if not source.exists():
            logger.error("%s not found - run `transform` first.", source)
            return 1
        df = pd.read_csv(source)

    write_tableau_extract(df)
    return 0


def cmd_refresh(args) -> int:
    """The scheduled path: scrape -> enrich -> transform -> load."""
    logger.info("=== refresh: scrape ===")
    if cmd_scrape(args) != 0:
        return 1
    if not INTERIM_SCRAPE.exists():
        logger.info("Nothing new - refresh finished early.")
        return 0

    if config.SPOTIFY.configured and not args.skip_enrich:
        logger.info("=== refresh: enrich ===")
        args.input = None
        cmd_enrich(args)
    else:
        logger.info("Skipping Spotify enrichment.")

    logger.info("=== refresh: transform ===")
    args.input = None
    args.output = None
    if cmd_transform(args) != 0:
        return 1

    logger.info("=== refresh: load ===")
    args.input = None
    return cmd_load(args)


# ── argument parsing ────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bandcamp_aotd",
        description="Bandcamp Album of the Day analytics pipeline",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="apply schema.sql and views.sql")
    init_db.set_defaults(func=cmd_init_db)

    scrape = subparsers.add_parser("scrape", help="crawl Bandcamp Daily for new articles")
    scrape.add_argument("--full", action="store_true",
                        help="ignore what's already loaded and crawl everything")
    scrape.add_argument("--max-pages", type=int, default=None, help="stop after N index pages")
    scrape.add_argument("--no-cache", action="store_true", help="re-download cached pages")
    scrape.set_defaults(func=cmd_scrape)

    enrich = subparsers.add_parser("enrich", help="attach Spotify catalog metadata")
    enrich.add_argument("--input", help="CSV to enrich (default: the last scrape)")
    enrich.set_defaults(func=cmd_enrich)

    transform = subparsers.add_parser("transform", help="build the analytics table")
    transform.add_argument("--input", help="CSV to transform")
    transform.add_argument("--output", help="where to write the analytics table")
    transform.set_defaults(func=cmd_transform)

    load = subparsers.add_parser("load", help="upsert the analytics table into Postgres")
    load.add_argument("--input", help="analytics CSV to load")
    load.set_defaults(func=cmd_load)

    backfill = subparsers.add_parser("backfill", help="load the historic CSV export")
    backfill.add_argument("--input", help="legacy CSV (default: the enriched export)")
    backfill.add_argument("--dry-run", action="store_true", help="transform but do not write")
    backfill.set_defaults(func=cmd_backfill)

    export = subparsers.add_parser("export", help="write the Tableau extract")
    export.add_argument("--input", help="analytics CSV to export")
    export.add_argument("--from-db", action="store_true", help="read from Postgres instead")
    export.set_defaults(func=cmd_export)

    refresh = subparsers.add_parser("refresh", help="scrape -> enrich -> transform -> load")
    refresh.add_argument("--full", action="store_true")
    refresh.add_argument("--max-pages", type=int, default=None)
    refresh.add_argument("--no-cache", action="store_true")
    refresh.add_argument("--skip-enrich", action="store_true")
    refresh.set_defaults(func=cmd_refresh, input=None, output=None)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    config.ensure_directories()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        logger.warning("Interrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001 - top-level handler
        logger.error("%s: %s", type(exc).__name__, exc)
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())

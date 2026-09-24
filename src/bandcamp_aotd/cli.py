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
    """Attach Spotify metadata to a scraped or legacy CSV.

    Two input shapes are supported, because the project has both:

    * a fresh scrape, which already uses snake_case ``artist`` / ``album``
    * a legacy export, which uses ``Artist`` / ``Album`` (pass ``--legacy``)

    ``--legacy`` matters for more than column names. Resume works by
    DataFrame index, so the rows have to arrive in the same order they did on
    the run being resumed. Reading the legacy CSV through ``load_legacy_csv``
    renames columns without reordering or dropping anything, which keeps the
    existing checkpoint aligned.
    """
    from .enrich.spotify import SpotifyClient, SpotifyRunAborted
    from .legacy import load_legacy_csv

    source = Path(args.input) if args.input else INTERIM_SCRAPE
    if not source.exists():
        logger.error("%s not found - run `scrape` first or pass --input.", source)
        return 1
    if not config.SPOTIFY.configured:
        logger.error("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET are not set. "
                     "Copy .env.example to .env and fill them in.")
        return 1

    df = load_legacy_csv(source) if args.legacy else pd.read_csv(source)

    missing = {"artist", "album"} - set(df.columns)
    if missing:
        logger.error(
            "%s has no %s column. If this is one of the original exports "
            "(Artist/Album headers), re-run with --legacy.",
            source.name, "/".join(sorted(missing)),
        )
        return 1

    # Re-enriching an already-enriched file would concat duplicate spotify_*
    # columns. Drop the old ones and let this run rebuild them.
    stale = [c for c in df.columns if c.startswith("spotify_")]
    if stale:
        logger.info("Dropping %d existing spotify_* columns before re-enriching", len(stale))
        df = df.drop(columns=stale)

    destination = Path(args.output) if args.output else INTERIM_ENRICHED
    client = SpotifyClient()
    client.call_budget = args.max_calls
    if args.max_calls:
        logger.info("Call budget for this run: %d", args.max_calls)

    try:
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
    except SpotifyRunAborted as exc:
        logger.error("Run stopped: %s", exc)
        logger.error("Progress is checkpointed. Re-run this exact command after "
                     "the cooldown and it will pick up where it left off.")
        return 1

    config.ensure_directories()
    enriched.to_csv(destination, index=False)

    matched = enriched["spotify_match_status"].eq("matched")
    errored = enriched["spotify_match_status"].astype(str).str.startswith("error")
    logger.info("Wrote %d enriched rows to %s", len(enriched), destination)
    logger.info("Album match rate: %.1f%% matched, %.1f%% no match, %.1f%% errored",
                100 * matched.mean(),
                100 * enriched["spotify_match_status"].eq("no_match").mean(),
                100 * errored.mean())
    if errored.any():
        logger.warning("%d rows still errored - re-run this command to retry just those.",
                       int(errored.sum()))
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
    from .load import export_views, read_analytics_table, write_tableau_extract

    if args.views:
        if not config.DATABASE.configured:
            logger.error("--views reads from Postgres; set DATABASE_URL in .env first.")
            return 1
        written = export_views()
        return 0 if written else 1

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
    enrich.add_argument("--output", help="where to write the enriched CSV")
    enrich.add_argument("--legacy", action="store_true",
                        help="input uses the original Artist/Album headers")
    enrich.add_argument("--max-calls", type=int, default=None,
                        help="stop after N API calls, to stay under Spotify's "
                             "Development Mode quota (try 300)")
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
    export.add_argument("--views", action="store_true",
                        help="export every analytics view as its own CSV (for Tableau)")
    export.set_defaults(func=cmd_export)

    refresh = subparsers.add_parser("refresh", help="scrape -> enrich -> transform -> load")
    refresh.add_argument("--full", action="store_true")
    refresh.add_argument("--max-pages", type=int, default=None)
    refresh.add_argument("--no-cache", action="store_true")
    refresh.add_argument("--skip-enrich", action="store_true")
    # A scheduled refresh always works on freshly scraped (snake_case) data,
    # so legacy is False here — but it must be *set*, or cmd_enrich raises
    # AttributeError when refresh delegates to it.
    refresh.set_defaults(func=cmd_refresh, input=None, output=None,
                         legacy=False, max_calls=None, views=False)

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

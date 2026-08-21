"""Central configuration.

Every path and credential the pipeline needs is resolved here, once, so no
module has to guess where the project root is or reach into ``os.environ`` on
its own. Secrets come from ``.env`` (git-ignored); everything else has a
default that works on a fresh clone with no setup at all.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# config.py lives at <root>/src/bandcamp_aotd/config.py -> three parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

# ── Project layout ──────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
HTML_CACHE_DIR = RAW_DIR / "html_cache"

DB_DIR = PROJECT_ROOT / "db"
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# ── Canonical file names ────────────────────────────────────────────────────
LEGACY_ARTICLES_CSV = PROCESSED_DIR / "aotd_articles.csv"
ENRICHED_CSV = PROCESSED_DIR / "aotd_articles_enriched.csv"
ANALYTICS_CSV = PROCESSED_DIR / "aotd_analytics.csv"
SPOTIFY_ALBUM_CHECKPOINT = INTERIM_DIR / "spotify_checkpoint.csv"
SPOTIFY_ARTIST_CHECKPOINT = INTERIM_DIR / "spotify_artist_checkpoint.csv"

# ── Source ──────────────────────────────────────────────────────────────────
BANDCAMP_BASE_URL = "https://daily.bandcamp.com"
BANDCAMP_INDEX_PATH = "/album-of-the-day"
USER_AGENT = os.getenv(
    "BANDCAMP_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
# Politeness: Bandcamp Daily is a small editorial site, not an API. These
# defaults keep the crawl comfortably under one request per second.
REQUEST_DELAY_SECONDS = float(os.getenv("BANDCAMP_REQUEST_DELAY", "0.75"))
INDEX_PAGE_DELAY_SECONDS = float(os.getenv("BANDCAMP_INDEX_DELAY", "2.0"))
MAX_INDEX_PAGES = int(os.getenv("BANDCAMP_MAX_INDEX_PAGES", "500"))


@dataclass(frozen=True)
class SpotifyConfig:
    client_id: str | None = field(
        default_factory=lambda: os.getenv("SPOTIFY_CLIENT_ID")
    )
    client_secret: str | None = field(
        default_factory=lambda: os.getenv("SPOTIFY_CLIENT_SECRET")
    )

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


@dataclass(frozen=True)
class DatabaseConfig:
    """Supabase / Postgres connection.

    A single ``DATABASE_URL`` keeps local development and Supabase
    interchangeable - point it at either and nothing else changes.
    """

    url: str | None = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    schema: str = field(default_factory=lambda: os.getenv("DB_SCHEMA", "bandcamp"))

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def require_url(self) -> str:
        if not self.url:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env and paste the "
                "connection string from Supabase > Project Settings > Database."
            )
        return self.url


SPOTIFY = SpotifyConfig()
DATABASE = DatabaseConfig()


def ensure_directories() -> None:
    """Create every directory the pipeline writes to. Safe to call repeatedly."""
    for path in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, EXPORTS_DIR,
                 HTML_CACHE_DIR, FIGURES_DIR):
        path.mkdir(parents=True, exist_ok=True)

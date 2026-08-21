-- ============================================================================
-- Bandcamp Album of the Day - warehouse schema (PostgreSQL / Supabase)
-- ============================================================================
--
-- Design notes
-- ------------
-- The grain of the warehouse is one row per published article. That is a
-- genuinely small table (~2.3k rows, growing by ~5/week), so this is modelled
-- as a wide fact table with conformed dimensions rather than a strict star:
-- the joins a star would buy are not worth the load complexity at this size,
-- and Tableau extracts and the web app both want the flat shape anyway.
--
-- Dimensions still exist where they earn their keep - places, labels and
-- authors are reused across rows and carry attributes of their own (a place
-- has coordinates; an author has an activity window).
--
-- Everything is idempotent: every table has a natural key and every load path
-- is INSERT ... ON CONFLICT DO UPDATE, so re-running a refresh over an
-- overlapping date range updates rows instead of duplicating them.
--
-- Apply with:  psql "$DATABASE_URL" -f db/schema.sql
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS bandcamp;
SET search_path TO bandcamp, public;


-- ----------------------------------------------------------------------------
-- dim_place - one row per distinct cleaned location
-- ----------------------------------------------------------------------------
-- Split out because the same city appears on dozens of articles and because
-- geocoded coordinates belong to the place, not to the article. Keeping
-- lat/lon here means geocoding runs once per place instead of once per row.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_place (
    place_id        BIGSERIAL PRIMARY KEY,
    location_clean  TEXT NOT NULL UNIQUE,
    city            TEXT,
    state           TEXT,
    country         TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    geocoded_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dim_place_country ON dim_place (country);
CREATE INDEX IF NOT EXISTS idx_dim_place_city    ON dim_place (city);


-- ----------------------------------------------------------------------------
-- dim_author - one row per Bandcamp Daily contributor
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_author (
    author_id       BIGSERIAL PRIMARY KEY,
    author_name     TEXT NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ----------------------------------------------------------------------------
-- dim_label - one row per record label
-- ----------------------------------------------------------------------------
-- 'Independent Artist' is a real member of this dimension, flagged rather
-- than special-cased, so "indie share" is a filter instead of a string
-- comparison repeated in every query.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_label (
    label_id        BIGSERIAL PRIMARY KEY,
    label_name      TEXT NOT NULL UNIQUE,
    is_independent  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ----------------------------------------------------------------------------
-- fact_article - the grain: one published Album of the Day article
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_article (
    -- Natural key: SHA-1 of (published_date | artist | album). Deterministic
    -- across sources, which is what makes the upsert safe. See
    -- src/bandcamp_aotd/transform/identity.py.
    article_id      TEXT PRIMARY KEY,
    article_url     TEXT,
    article_slug    TEXT,

    -- Calendar (pre-computed so Tableau and the app agree on week boundaries)
    published_date  DATE NOT NULL,
    year            SMALLINT,
    quarter         SMALLINT,
    month           SMALLINT,
    month_name      TEXT,
    iso_week        SMALLINT,
    day_of_month    SMALLINT,
    day_of_week_num SMALLINT,
    day_of_week     TEXT,

    -- Editorial
    author_id       BIGINT REFERENCES dim_author (author_id),
    title           TEXT,
    genre_tag       TEXT,

    -- Release
    artist          TEXT,
    album           TEXT,
    label_id        BIGINT REFERENCES dim_label (label_id),
    is_independent  BOOLEAN,

    -- Geography
    place_id        BIGINT REFERENCES dim_place (place_id),
    label_location_raw TEXT,

    -- Spotify enrichment
    spotify_match_status            TEXT,
    spotify_id                      TEXT,
    spotify_url                     TEXT,
    spotify_artist_id               TEXT,
    spotify_match_artist            TEXT,
    spotify_match_album             TEXT,
    spotify_release_date            TEXT,
    spotify_release_date_precision  TEXT,
    spotify_album_type              TEXT,
    spotify_total_tracks            SMALLINT,
    spotify_image_url               TEXT,
    spotify_upc                     TEXT,
    spotify_ean                     TEXT,
    spotify_copyright               TEXT,
    spotify_artist_status           TEXT,
    spotify_artist_image_url        TEXT,
    spotify_artist_url              TEXT,

    -- Lineage
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fact_article_date      ON fact_article (published_date DESC);
CREATE INDEX IF NOT EXISTS idx_fact_article_author    ON fact_article (author_id);
CREATE INDEX IF NOT EXISTS idx_fact_article_place     ON fact_article (place_id);
CREATE INDEX IF NOT EXISTS idx_fact_article_label     ON fact_article (label_id);
CREATE INDEX IF NOT EXISTS idx_fact_article_genre     ON fact_article (genre_tag);
CREATE INDEX IF NOT EXISTS idx_fact_article_year      ON fact_article (year);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_article_url
    ON fact_article (article_url) WHERE article_url IS NOT NULL;


-- ----------------------------------------------------------------------------
-- pipeline_run - an audit trail for every refresh
-- ----------------------------------------------------------------------------
-- Without this, "is the dashboard stale?" is unanswerable. The web app reads
-- the latest row to show a "data as of" timestamp, and a failed run leaves a
-- record rather than disappearing.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id          BIGSERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    stage           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    rows_scraped    INTEGER DEFAULT 0,
    rows_inserted   INTEGER DEFAULT 0,
    rows_updated    INTEGER DEFAULT 0,
    message         TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_started ON pipeline_run (started_at DESC);


-- ----------------------------------------------------------------------------
-- Keep updated_at honest
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_fact_article_updated_at ON fact_article;
CREATE TRIGGER trg_fact_article_updated_at
    BEFORE UPDATE ON fact_article
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

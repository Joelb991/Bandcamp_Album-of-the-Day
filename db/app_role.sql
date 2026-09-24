-- ============================================================================
-- Bandcamp Album of the Day - read-only role for the web app
-- ============================================================================
--
-- The app only ever reads the analytics views. A view runs with its owner's
-- privileges, so granting SELECT on the views alone is enough: this role can
-- read the semantic layer but cannot touch fact_article, the dimensions or
-- pipeline_run directly, and it cannot write anything.
--
-- Apply once, choosing a password:
--   psql "$DATABASE_URL" -v app_password='choose-a-long-password' -f db/app_role.sql
--
-- Then connect through the Supabase pooler as  aotd_app.<project-ref>  and put
-- that connection string in the app's DATABASE_URL.
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aotd_app') THEN
        CREATE ROLE aotd_app LOGIN;
    END IF;
END
$$;

ALTER ROLE aotd_app WITH LOGIN PASSWORD :'app_password';
ALTER ROLE aotd_app SET default_transaction_read_only = on;
ALTER ROLE aotd_app SET statement_timeout = '15s';

GRANT USAGE ON SCHEMA bandcamp TO aotd_app;
GRANT SELECT ON
    bandcamp.vw_article,
    bandcamp.vw_coverage_by_country,
    bandcamp.vw_city_genre_specialisation,
    bandcamp.vw_author_profile,
    bandcamp.vw_genre_trend,
    bandcamp.vw_label_leaderboard,
    bandcamp.vw_latest_features,
    bandcamp.vw_pipeline_health
TO aotd_app;

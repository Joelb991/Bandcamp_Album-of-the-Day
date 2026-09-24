import "server-only";
import { cache } from "react";
import { sql } from "./db";

/*
 * Every query reads from the `bandcamp` views (db/views.sql), never from the
 * base tables. Numbers are cast in SQL (::int, ::float8, ::text) so what
 * reaches React is plain JSON - no bigint strings, no Date objects.
 */

export type Health = {
  totalArticles: number;
  latestArticleDate: string;
  lastLoadAt: string;
  spotifyMatchRate: number;
  locationCoverageRate: number;
  lastRunStatus: string | null;
};

export const getHealth = cache(async (): Promise<Health> => {
  const [row] = await sql()<Health[]>`
    SELECT
      total_articles::int             AS "totalArticles",
      latest_article_date::text       AS "latestArticleDate",
      last_load_at::text              AS "lastLoadAt",
      spotify_match_rate::float8      AS "spotifyMatchRate",
      location_coverage_rate::float8  AS "locationCoverageRate",
      last_run_status                 AS "lastRunStatus"
    FROM bandcamp.vw_pipeline_health`;
  return row;
});

export type Headline = {
  features: number;
  countries: number;
  writers: number;
  labels: number;
  indieShare: number;
  usShare: number;
  top3Share: number;
  top15WriterShare: number;
  firstDate: string;
  lastDate: string;
  untaggedShare: number;
};

export const getHeadline = cache(async (): Promise<Headline> => {
  const [row] = await sql()<Headline[]>`
    WITH top_countries AS (
      SELECT features FROM bandcamp.vw_coverage_by_country
      ORDER BY features DESC LIMIT 3
    ),
    top_writers AS (
      SELECT reviews FROM bandcamp.vw_author_profile
      ORDER BY reviews DESC LIMIT 15
    )
    SELECT
      COUNT(*)::int                                                     AS features,
      COUNT(DISTINCT country)::int                                      AS countries,
      COUNT(DISTINCT author)::int                                       AS writers,
      COUNT(DISTINCT record_label) FILTER (WHERE NOT is_independent)::int AS labels,
      (100 * AVG(is_independent::int))::float8                          AS "indieShare",
      (100.0 * COUNT(*) FILTER (WHERE country = 'United States')
             / NULLIF(COUNT(country), 0))::float8                       AS "usShare",
      -- From counts, not by summing the view's already-rounded percentages.
      (100.0 * (SELECT SUM(features) FROM top_countries) / NULLIF(COUNT(country), 0))::float8 AS "top3Share",
      (100.0 * (SELECT SUM(reviews) FROM top_writers) / COUNT(*))::float8 AS "top15WriterShare",
      MIN(published_date)::text                                         AS "firstDate",
      MAX(published_date)::text                                         AS "lastDate",
      (100.0 * COUNT(*) FILTER (WHERE genre_tag IS NULL) / COUNT(*))::float8 AS "untaggedShare"
    FROM bandcamp.vw_article`;
  return row;
});

export type YearRow = {
  year: number;
  features: number;
  located: number;
  usShare: number;
  indieShare: number;
};

/** Per-year shares. 2011 (9 articles) is excluded - it is too thin to plot. */
export const getYearly = cache(async (): Promise<YearRow[]> => {
  return sql()<YearRow[]>`
    SELECT
      year::int,
      COUNT(*)::int                                   AS features,
      COUNT(country)::int                             AS located,
      (100.0 * COUNT(*) FILTER (WHERE country = 'United States')
             / NULLIF(COUNT(country), 0))::float8     AS "usShare",
      (100 * AVG(is_independent::int))::float8        AS "indieShare"
    FROM bandcamp.vw_article
    WHERE year IS NOT NULL
    GROUP BY year
    HAVING COUNT(country) >= 20
    ORDER BY year`;
});

export type RosterShift = { writers: number; before: number; after: number; continuingShare: number };

/**
 * Was the 2024 drop in US share a change of writers? Compares the US share of
 * writers active both in 2018-23 and since 2024, before and after.
 */
export const getRosterShift = cache(async (): Promise<RosterShift> => {
  const [row] = await sql()<RosterShift[]>`
    WITH located AS (
      SELECT author, year, (country = 'United States')::int AS us
      FROM bandcamp.vw_article
      WHERE country IS NOT NULL AND author IS NOT NULL
    ),
    continuing AS (
      SELECT author FROM located WHERE year BETWEEN 2018 AND 2023
      INTERSECT
      SELECT author FROM located WHERE year >= 2024
    )
    SELECT
      (SELECT COUNT(*) FROM continuing)::int AS writers,
      (100 * AVG(us) FILTER (WHERE year BETWEEN 2018 AND 2023
                              AND author IN (SELECT author FROM continuing)))::float8 AS before,
      (100 * AVG(us) FILTER (WHERE year >= 2024
                              AND author IN (SELECT author FROM continuing)))::float8 AS after,
      (100.0 * COUNT(*) FILTER (WHERE year >= 2024 AND author IN (SELECT author FROM continuing))
             / NULLIF(COUNT(*) FILTER (WHERE year >= 2024), 0))::float8 AS "continuingShare"
    FROM located`;
  return row;
});

export type Scene = {
  city: string;
  state: string | null;
  country: string;
  genre: string;
  features: number;
  cityFeatures: number;
  cityShare: number;
  globalShare: number;
  lift: number;
};

export const getScenes = cache(async (limit = 12): Promise<Scene[]> => {
  return sql()<Scene[]>`
    SELECT
      city, state, country,
      genre_tag              AS genre,
      features::int,
      city_features::int     AS "cityFeatures",
      city_share::float8     AS "cityShare",
      global_share::float8   AS "globalShare",
      lift::float8
    FROM bandcamp.vw_city_genre_specialisation
    ORDER BY lift DESC, features DESC
    LIMIT ${limit}`;
});

export type Writer = {
  author: string;
  reviews: number;
  genres: number;
  countries: number;
  indieShare: number;
  entropy: number;
};

export const getWriters = cache(async (minReviews = 15): Promise<Writer[]> => {
  return sql()<Writer[]>`
    SELECT
      author,
      reviews::int,
      distinct_genres::int          AS genres,
      distinct_countries::int       AS countries,
      (100 * indie_share)::float8   AS "indieShare",
      genre_entropy_bits::float8    AS entropy
    FROM bandcamp.vw_author_profile
    WHERE reviews >= ${minReviews} AND genre_entropy_bits IS NOT NULL
    ORDER BY reviews DESC`;
});

export type CountryStat = {
  country: string;
  features: number;
  artists: number;
  labels: number;
  genres: number;
  indieShare: number;
  pct: number;
  firstFeature: string;
  latestFeature: string;
  topGenres: { genre: string; n: number }[];
  topCities: { city: string; n: number }[];
  covers: { id: string; img: string; artist: string; album: string }[];
};

export const getCountries = cache(async (): Promise<CountryStat[]> => {
  return sql()<CountryStat[]>`
    WITH genres AS (
      SELECT country, genre_tag AS genre, COUNT(*)::int AS n,
             ROW_NUMBER() OVER (PARTITION BY country ORDER BY COUNT(*) DESC, genre_tag) AS rk
      FROM bandcamp.vw_article
      WHERE country IS NOT NULL AND genre_tag IS NOT NULL
      GROUP BY country, genre_tag
    ),
    cities AS (
      SELECT country, city, COUNT(*)::int AS n,
             ROW_NUMBER() OVER (PARTITION BY country ORDER BY COUNT(*) DESC, city) AS rk
      FROM bandcamp.vw_article
      WHERE country IS NOT NULL AND city IS NOT NULL
      GROUP BY country, city
    ),
    covers AS (
      SELECT country, LEFT(article_id, 10) AS id, artist, album,
             SUBSTRING(spotify_image_url FROM 'ab67616d0000b273(.+)$') AS img,
             ROW_NUMBER() OVER (PARTITION BY country ORDER BY published_date DESC) AS rk
      FROM bandcamp.vw_article
      WHERE country IS NOT NULL AND spotify_image_url IS NOT NULL
    )
    SELECT
      c.country,
      c.features::int,
      c.distinct_artists::int                 AS artists,
      c.distinct_labels::int                  AS labels,
      c.distinct_genres::int                  AS genres,
      (100 * c.indie_share)::float8           AS "indieShare",
      c.pct_of_all_features::float8           AS pct,
      c.first_feature::text                   AS "firstFeature",
      c.latest_feature::text                  AS "latestFeature",
      COALESCE((SELECT json_agg(json_build_object('genre', g.genre, 'n', g.n) ORDER BY g.rk)
                FROM genres g WHERE g.country = c.country AND g.rk <= 5), '[]') AS "topGenres",
      COALESCE((SELECT json_agg(json_build_object('city', t.city, 'n', t.n) ORDER BY t.rk)
                FROM cities t WHERE t.country = c.country AND t.rk <= 5), '[]') AS "topCities",
      COALESCE((SELECT json_agg(json_build_object('id', v.id, 'img', v.img, 'artist', v.artist, 'album', v.album) ORDER BY v.rk)
                FROM covers v WHERE v.country = c.country AND v.rk <= 6), '[]') AS covers
    FROM bandcamp.vw_coverage_by_country c
    ORDER BY c.features DESC, c.country`;
});

/**
 * One row per feature, with short keys - this array ships to the browser for
 * client-side search, so every byte counts. `img` is the Spotify image hash
 * (the CDN prefix picks the size) and `sp` is the Spotify album id.
 */
export type Feature = {
  id: string;
  d: string;
  artist: string;
  album: string;
  genre: string | null;
  label: string | null;
  indie: boolean;
  city: string | null;
  state: string | null;
  country: string | null;
  author: string | null;
  img: string | null;
  sp: string | null;
};

export const getFeatures = cache(async (): Promise<Feature[]> => {
  return sql()<Feature[]>`
    SELECT
      LEFT(article_id, 10)                                        AS id,
      published_date::text                                        AS d,
      artist,
      album,
      genre_tag                                                   AS genre,
      record_label                                                AS label,
      is_independent                                              AS indie,
      city,
      state,
      country,
      author,
      SUBSTRING(spotify_image_url FROM 'ab67616d0000b273(.+)$')   AS img,
      SUBSTRING(spotify_url FROM 'album/([A-Za-z0-9]+)')          AS sp
    FROM bandcamp.vw_article
    ORDER BY published_date DESC, artist`;
});

export type Latest = Pick<Feature, "id" | "d" | "artist" | "album" | "img" | "city" | "country">;

export const getLatestWithCovers = cache(async (limit = 12): Promise<Latest[]> => {
  return sql()<Latest[]>`
    SELECT
      LEFT(article_id, 10)                                        AS id,
      published_date::text                                        AS d,
      artist, album, city, country,
      SUBSTRING(spotify_image_url FROM 'ab67616d0000b273(.+)$')   AS img
    FROM bandcamp.vw_latest_features
    WHERE spotify_image_url IS NOT NULL
    ORDER BY published_date DESC
    LIMIT ${limit}`;
});

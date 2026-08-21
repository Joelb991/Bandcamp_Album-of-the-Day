# Data Dictionary

Grain: **one row per published Bandcamp Daily *Album of the Day* article.**
2,287 rows covering 2011-10-28 to 2026-05-26.

Null rates below are measured on the current dataset. Where a null means
something specific, it says so — a gap that is explained is usable; a gap that
isn't is a landmine.

---

## Identity

| Column | Type | Null | Distinct | Description |
|---|---|---|---|---|
| `article_id` | text | 0% | 2,287 | **Primary key.** SHA-1 (16 hex chars) of normalised `published_date \| artist \| album`. Deterministic across sources — this is what makes loads idempotent. |
| `article_url` | text | 100% | 0 | Canonical article URL. Empty for every historic row: the original export predates URL capture. Populated for anything scraped from now on. |
| `article_slug` | text | 100% | 0 | URL slug. Same provenance as above. |

> The 100% null on `article_url` is exactly why the warehouse keys on a content
> hash. See [`transform/identity.py`](../src/bandcamp_aotd/transform/identity.py).

## Calendar

All derived from `published_date` in the pipeline, not in the BI tool — so
Tableau, the web app and the notebooks agree on week boundaries.

| Column | Type | Null | Description |
|---|---|---|---|
| `published_date` | date | 0% | Publication date. 2,283 distinct across 2,287 rows — a few days carry two features. |
| `year` | int | 0% | 2011–2026 |
| `quarter` | int | 0% | 1–4 |
| `month` | int | 0% | 1–12 |
| `month_name` | text | 0% | "January" … |
| `iso_week` | int | 0% | ISO week number, 1–52 |
| `day_of_month` | int | 0% | 1–31 |
| `day_of_week_num` | int | 0% | Monday = 0 |
| `day_of_week` | text | 0% | "Monday" … |

## Editorial

| Column | Type | Null | Distinct | Description |
|---|---|---|---|---|
| `author` | text | 0% | 343 | Bandcamp Daily contributor. Long-tailed: the top 15 wrote 29.5% of everything. |
| `title` | text | 0% | 2,287 | Headline, with site branding and the "Album of the Day:" prefix stripped. |
| `genre_tag` | text | **13.6%** | 25 | Primary genre from the `article:tag` meta property. **Nulls are genuine** — older articles were published before Bandcamp tagged them. Filter these out of any genre statistic rather than treating them as a category. |

## Release

| Column | Type | Null | Distinct | Description |
|---|---|---|---|---|
| `artist` | text | 0% | 1,991 | From the headline, split on the first comma. Fewer distinct than rows: some artists are featured more than once. |
| `album` | text | 0% | 2,280 | Same split; typographic quotes stripped. |
| `record_label` | text | 0% | 585 | Credited label, or `Independent Artist` for self-released records. |
| `is_independent` | bool | 0% | 2 | `record_label == 'Independent Artist'`. **66.2% true.** Derived in the pipeline so it is a real boolean, not a string comparison repeated in every query. |

> **Read `is_independent` carefully.** It is derived from a rule: if the parsed
> artist and the credited label are the same entity, the record is treated as
> self-released. That is right in the overwhelming majority of cases, but it
> also absorbs rows where the label field failed to parse. Treat 66.2% as a
> well-founded estimate, not a census.

## Geography

| Column | Type | Null | Distinct | Description |
|---|---|---|---|---|
| `label_location_raw` | text | 3.5% | 422 | The label's self-reported location, exactly as typed. Kept for auditability. |
| `location_clean` | text | 3.5% | 407 | After the nine-step cleaner. 15 duplicate spellings collapsed. |
| `city` | text | **17.3%** | 320 | Null when the source gave only a country or region — not a pipeline failure. |
| `state` | text | **43.0%** | 51 | US states and Canadian provinces only. Null for everywhere else by design. |
| `country` | text | 3.5% | 82 | Resolved country. **96.5% coverage; zero values fail to resolve.** |

> **The measurement caveat that matters most:** this is the *label's* location,
> not the artist's. An artist in Lagos signed to a Berlin label registers as
> Berlin. Conclusions drawn from these columns are about where the
> infrastructure of independent music sits, not where musicians live.

UK constituent countries (England, Scotland, Wales, Northern Ireland) appear as
`country` values in their own right, matching how they occur standalone in the
source and how mapping tools expect them.

## Spotify enrichment

| Column | Type | Null | Description |
|---|---|---|---|
| `spotify_match_status` | text | 0% | `matched` · `no_match` · `error: …`. **Filter on this before trusting any column below.** |
| `spotify_id` | text | 77% | Spotify album ID |
| `spotify_url` | text | 77% | Public album link |
| `spotify_artist_id` | text | 77% | Spotify artist ID |
| `spotify_match_artist` | text | 77% | Artist name **as Spotify has it** — compare against `artist` to catch false positives |
| `spotify_match_album` | text | 77% | Album name as Spotify has it |
| `spotify_release_date` | text | 77% | ISO date; precision varies |
| `spotify_release_date_precision` | text | 77% | `day` or `year` |
| `spotify_album_type` | text | 77% | `album` · `single` · `compilation` |
| `spotify_total_tracks` | int | 77% | Track count |
| `spotify_image_url` | text | 77% | Cover art |
| `spotify_upc` / `spotify_ean` / `spotify_copyright` | text | 100% | Require `full_details=True` (a second API call per row). Not currently populated. |
| `spotify_artist_status` | text | 77% | `matched` · `no_id` · `error: …` |
| `spotify_artist_image_url` | text | 77% | Artist photo |
| `spotify_artist_url` | text | 77% | Artist profile link |

### About that 77%

Two separate causes, and they mean different things:

1. **Genuine absence.** Plenty of Bandcamp Daily picks are not on Spotify —
   which is much of the point of Bandcamp. 169 rows are confirmed `no_match`.
   This is a finding, not a gap.
2. **An interrupted run.** 1,592 rows carry an `error:` status from a run that
   hit a 24-hour Spotify rate limit. Re-running
   `python -m bandcamp_aotd enrich` resumes from the checkpoint and retries
   exactly those rows.

Only 527 rows are confirmed matched today. **Do not report a "23% Spotify
availability" figure** — the denominator is contaminated by the failed run.

### Deliberately omitted

`Album.genres`, `Album.label`, `Album.popularity` and the artist equivalents
are deprecated in Spotify's current API and return empty or unreliable values.
The Bandcamp `genre_tag` and `record_label` columns are the better source and
are already present.

---

## Warehouse tables

| Table | Rows | Key |
|---|---|---|
| `fact_article` | 2,287 | `article_id` |
| `dim_place` | 407 | `location_clean` |
| `dim_author` | 343 | `author_name` |
| `dim_label` | 585 | `label_name` |
| `pipeline_run` | grows | `run_id` |

`dim_place.latitude` / `longitude` exist and are currently unpopulated —
reserved for the geocoding step described in
[`roadmap.md`](roadmap.md).

## Views

| View | Purpose |
|---|---|
| `vw_article` | Denormalised base view; everything else builds on it |
| `vw_coverage_by_country` | Choropleth source |
| `vw_city_genre_specialisation` | City/genre lift, with count floors applied |
| `vw_author_profile` | Reviews, diversity (Shannon entropy), indie share per writer |
| `vw_genre_trend` | Genre share by year |
| `vw_label_leaderboard` | Most-featured labels |
| `vw_latest_features` | The web app's front page |
| `vw_pipeline_health` | Freshness and match rates |

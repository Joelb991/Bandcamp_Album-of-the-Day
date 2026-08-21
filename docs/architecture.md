# Architecture

Why the pipeline is shaped the way it is, and what went wrong on the way there.

---

## 1. The constraint that shapes everything

Bandcamp Daily has no API. The only way to get the archive is to read ~2,300
HTML pages belonging to a small editorial publisher who did not ask to be
scraped.

That single fact drives three decisions:

| Decision | Consequence |
|---|---|
| Cache every fetched page to disk | The archive is crawled **once**, ever. Re-parsing is free and offline. |
| Crawl incrementally, newest-first | A weekly refresh costs one HTTP request, not five hundred. |
| Sub-1-req/s pacing, `Retry-After` honoured | The crawl does not get the project's IP banned. |

A scraper that is impolite is not a working scraper — it works until it
doesn't, and then the whole project stops.

---

## 2. Stage design

### Extract — `src/bandcamp_aotd/extract/`

Three modules, one job each.

**`discover.py`** walks `/album-of-the-day?page=N`. Because the index is
newest-first, passing `known_urls` turns a full crawl into an incremental one:
the crawler stops after `stop_after_known` consecutive familiar URLs (default
30 — one full page). One page is the right threshold: stopping on a single
known URL would be fooled by any out-of-order republish, and reading further
buys nothing.

**`fetch.py`** downloads each page and writes it to
`data/raw/html_cache/<slug>.html`. Everything downstream reads from that cache.

**`parse.py`** extracts seven fields. Each has a **primary regex** — the
expression that has been producing this dataset correctly since 2021 — and a
**meta-tag fallback** reading Open Graph properties. Regex first keeps
historical output byte-identical; the fallback means a Bandcamp redesign
degrades the pipeline instead of breaking it.

No extractor raises. A missing field becomes `None` and the row records why in
`parse_status`. One malformed article cannot end a 2,300-page crawl.

### Transform — `src/bandcamp_aotd/transform/`

Runs in a fixed order, defined once in `build_analytics_table`:

1. `text.py` — HTML entities, smart quotes, whitespace
2. `dates.py` — parse the date, derive nine calendar attributes
3. `locations.py` — the nine-step location cleaner, then city/state/country
4. `text.add_label_features` — the `is_independent` flag
5. `identity.py` — mint `article_id`, de-duplicate
6. Reject rows with no publication date, enforce the canonical schema

Steps 1–2 run **before** step 5 on purpose: the id is hashed from the
*normalised* date, artist and album, so cosmetic differences between the legacy
CSV and a fresh scrape resolve to the same key.

#### The location cleaner is the interesting part

`label_location_raw` is free text a label owner typed into their own Bandcamp
profile. 422 distinct values, containing:

- whitespace before commas (`"Osaka , Japan"`)
- CJK placenames (`"東京都, Japan"`)
- six spellings of Washington D.C.
- the Turkish dotted capital İ (U+0130)
- bare city names with no country (`"Chicago"`)
- accent-only duplicates (`"Bogota"` vs `"Bogotá"`)
- ambiguous regional codes (`"Kzn, South Africa"`, `"Ib, Spain"`)

Nine ordered steps reduce that to 407 values covering 82 countries with **zero
unresolved**. Order is load-bearing in two places:

**The Turkish İ must be replaced before title-casing.** Python decomposes
U+0130 under `str.title()` into `I` plus a combining dot. The result compares
unequal to everything, silently splitting İstanbul into two cities. No amount
of downstream cleaning recovers it.

**The lookup tables must run after title-casing.** Their keys are written in
title case; run them earlier and nothing matches.

Each step is a separate named function, so the sequence reads as documentation
and each rule is unit-tested alone. Every test case in `tests/test_locations.py`
is a real value that broke something.

### Enrich — `src/bandcamp_aotd/enrich/spotify.py`

One `/search` call per row resolves a Bandcamp `(artist, album)` pair to a
Spotify album; the search response already carries everything except UPC/EAN
and copyright text. Artists are enriched per *unique* artist, not per row.

Progress is checkpointed to CSV every 50 rows. Completed rows are skipped on
re-run; previously-errored rows are retried.

### Load — `src/bandcamp_aotd/load/postgres.py`

Dimensions are upserted first and their surrogate keys read back, then the fact
table goes in with `INSERT … ON CONFLICT (article_id) DO UPDATE`. Rows are sent
in batches of 1,000 via `execute_values`.

Every run writes to `pipeline_run`, including failures. Without that table,
"is the dashboard stale?" is unanswerable.

---

## 3. Data model

The grain is **one row per published article** — 2,287 rows growing by ~5 a
week. That is small, so this is a wide fact table with conformed dimensions
rather than a strict star. The joins a full star would buy are not worth the
load complexity at this size, and both Tableau extracts and the web app want
the flat shape anyway.

Dimensions exist where they earn their keep:

| Table | Why it is separate |
|---|---|
| `dim_place` | The same city appears on dozens of articles, and geocoded coordinates belong to the place, not the article — so geocoding runs once per place, not once per row. |
| `dim_author` | Reused across rows; carries its own attributes (activity window, entropy). |
| `dim_label` | Reused; `is_independent` is a dimension attribute, not a string comparison repeated in every query. |
| `pipeline_run` | Freshness and lineage. |

`db/views.sql` is the semantic layer. Tableau, the app and the notebooks all
read views, never `fact_article` directly, so each metric has exactly one
definition.

---

## 4. Two bugs worth documenting

Both were found by testing against a real Postgres rather than by reading the
code. Both are the kind that produce *plausible wrong numbers* rather than
errors, which is what makes them worth writing down.

### `execute_values` silently returned only the last batch

`psycopg2.extras.execute_values` splits rows across several statements.
`cursor.fetchall()` afterwards returns only the **final** statement's rows.

The first load reported *"287 inserted"* out of 2,287 — exactly the last batch
of 1,000-row pages. The rows were all there; the count was wrong.

The same pattern in `_upsert_dimension` was worse: it would have silently lost
the surrogate keys for every batch but the last, producing NULL foreign keys in
the fact table for any dimension exceeding 1,000 members. `dim_label` has 585
today. It would have broken quietly on growth, months later.

**Fix:** `execute_values(..., fetch=True)`, which collects results across every
batch.

### NaN became the string "NaN" in TEXT columns

psycopg2 adapts `float('nan')` to the PostgreSQL float literal `NaN`. Inserted
into a `TEXT` column, that becomes the four-character *string* `"NaN"` — so
`dim_place` acquired a city called NaN, which then appeared in the
city-specialisation ranking as a legitimate result with a lift of 22.

`pd.notna()` at DataFrame level does not fix this: `df.where(pd.notna(df),
None)` leaves NaN in place for float-typed columns.

**Fix:** a `_null_safe()` guard applied to every value handed to the driver.

### And one in the Spotify client

The original client caught a `Retry-After: 86109` (a 24-hour ban) with the
per-row error handler, wrote `"error: rate limited"` into that row, and
continued — burning through the remaining 1,592 rows in seconds, marking each
one failed, and poisoning the checkpoint with work that was never attempted.

A long rate limit is a **run-level** condition, not a row-level one. It now
raises `SpotifyRateLimitError`, which is deliberately not caught per row: the
checkpoint is flushed, the run stops, and re-running after the cooldown resumes
correctly. Default pacing dropped from ~10 req/s to ~3 req/s.

---

## 5. What this deliberately does not do

**No dbt.** The transformation logic is Python-heavy — Unicode normalisation,
ordered string cleaning, a hash key. dbt would mean either reimplementing that
in SQL badly, or wrapping Python models around it for no gain at 2,287 rows.

**No Airflow.** One weekly job with four stages is a cron line. Airflow would
be infrastructure to maintain in exchange for a UI.

**No strict star schema.** Covered above — wrong tool for this grain.

Each of these becomes the right call at a different scale. Being able to say
*why not yet* is more useful than adopting them because they look impressive.

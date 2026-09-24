"""Generate the analysis notebooks from source-controlled definitions.

Notebooks are JSON, which makes them miserable to review in a pull request and
easy to corrupt by hand. Keeping the *content* here as plain Python and
generating the .ipynb files means notebook changes show up as readable diffs.

Run:  python tools/build_notebooks.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"

BOOTSTRAP = """\
import sys
from pathlib import Path

# Make the pipeline package importable without installing it, so the notebook
# runs on a fresh clone. `pip install -e .` also works and is preferred.
PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bandcamp_aotd.logging_config import setup_logging

setup_logging()"""


def md(text):
    return {"cell_type": "markdown", "metadata": {},
            "source": text.splitlines(keepends=True)}


def code(text):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def _with_ids(cells, prefix):
    """Give every cell a stable id, keyed on position.

    nbformat 4.5+ requires cell ids. Deriving them from the notebook name and
    index (rather than random uuids) keeps regenerated notebooks diffing
    cleanly instead of showing every cell as changed.
    """
    return [dict(cell, id=f"{prefix}-{i:02d}") for i, cell in enumerate(cells)]


def notebook(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 01 - Data collection
# ═══════════════════════════════════════════════════════════════════════════
NB_01 = [
    md("""# 01 - Data Collection

**Source:** [Bandcamp Daily, *Album of the Day*](https://daily.bandcamp.com/album-of-the-day)
**Output:** one row per published article -> `data/interim/scraped_articles.csv`

Bandcamp Daily has published an Album of the Day almost every weekday since
2011. There is no API, so the archive has to be scraped. This notebook walks
through how, and why the crawler is built the way it is.

The scraping logic itself lives in `src/bandcamp_aotd/extract/` and is
imported here rather than defined inline. That is deliberate: the scheduled
refresh runs the exact same code this notebook demonstrates, so there is no
second copy to drift out of sync.

| Stage | Module | What it does |
|---|---|---|
| Discover | `extract/discover.py` | Walk the paginated index, collect article URLs |
| Fetch | `extract/fetch.py` | Download each article once, cache it on disk |
| Parse | `extract/parse.py` | Pull seven fields out of each page |

> **Running this end to end takes ~40 minutes on a cold cache** (2,300 articles
> at ~1 request/second). Everything below is safe to run repeatedly - the cache
> means the second pass is instant."""),

    code(BOOTSTRAP),

    md("""## 1. Discover article URLs

The archive is paginated 30 articles per page, newest first. Two design
decisions matter here:

**Politeness.** Bandcamp Daily is a small editorial site, not an API. The
session sends a real User-Agent, warms up cookies before paginating, sleeps
between requests, and honours `Retry-After` on a 429. A scraper that gets a
project's IP banned is not a working scraper.

**Incrementality.** Because the index is newest-first, a refresh only needs to
read until it starts seeing articles it already has. Passing `known_urls`
turns a 500-page crawl into a 1-page one — the difference between a weekly job
that costs one HTTP request and one that costs five hundred."""),

    code("""from bandcamp_aotd.extract import build_session, discover_article_urls

session = build_session()

# max_pages=2 keeps this demo to ~60 articles. Drop it for a full backfill.
urls = discover_article_urls(session, max_pages=2)

print(f"Found {len(urls)} article URLs")
urls[:3]"""),

    md("""### What an incremental refresh looks like

In production the pipeline hands `discover_article_urls` the URLs already in
the warehouse. The crawler stops after seeing one full page of familiar
articles — enough to be confident it has caught up without betting the whole
run on a single URL."""),

    code("""from bandcamp_aotd.load import fetch_known_article_urls

# Reads from Postgres; returns an empty set (and logs a warning) if the
# database isn't configured yet, so this cell is safe to run either way.
known = fetch_known_article_urls()
print(f"{len(known)} articles already in the warehouse")"""),

    md("""## 2. Fetch article pages

Every page is written to `data/raw/html_cache/<slug>.html` the first time it
is downloaded and read from disk afterwards.

This is the single most useful decision in the extract layer. Regexes against
scraped HTML *will* need fixing. Without a cache, every fix means re-crawling
2,300 pages; with one, re-parsing the whole archive takes seconds and can be
done offline, on a plane, with no risk of being rate limited."""),

    code("""from bandcamp_aotd.extract import fetch_articles

pages = list(fetch_articles(session, urls[:5]))
url, html = pages[0]

print(url)
print(f"{len(html):,} characters of HTML")"""),

    md("""## 3. Parse each page

Seven fields come out of each article:

| Field | Where it comes from |
|---|---|
| `published_date` | the byline |
| `title` | `<title>`, minus site branding and the "Album of the Day:" prefix |
| `artist` / `album` | the title, split on the first comma |
| `genre_tag` | the `article:tag` meta property |
| `record_label` | the album sidebar |
| `label_location_raw` | the label's self-reported location |
| `author` | the contributor byline |

Each extractor has a **primary regex** — the expression that has been pulling
this dataset correctly since 2021 — and a **meta-tag fallback**. If Bandcamp
reskins the site the regex goes quiet and the Open Graph path keeps the
pipeline alive. Keeping the regex first means historical output stays
byte-identical.

Nothing raises. A field that can't be found comes back `None` and the row
records why in `parse_status`, so one odd article can't kill a 2,300-page
crawl."""),

    code("""from bandcamp_aotd.extract import parse_article

record = parse_article(html, url)
record"""),

    md("""### The two business rules worth knowing about

Bandcamp headlines are formatted `Artist, "Album"` — but not always, and the
exceptions carry real meaning:

1. **No comma in the headline** (self-titled records, compilations) leaves
   artist and album identical. In that case the sidebar's label field is
   actually the artist's name, so it gets promoted.
2. **Artist and label are the same entity** means the record is self-released.
   It's stored as `Independent Artist`.

Rule 2 produces the `is_independent` flag, which turns out to be the most
interesting single dimension in the dataset — about two thirds of everything
Bandcamp Daily features is self-released."""),

    code("""from bandcamp_aotd.extract.parse import resolve_label_and_artist

# Rule 1: headline had no comma
print(resolve_label_and_artist("Untitled", "Untitled", "Boomkat"))

# Rule 2: artist is their own label
print(resolve_label_and_artist("Aphex Twin", "Syro", "Aphex Twin"))"""),

    md("""## 4. Run the full scrape

`scrape_articles` chains discover -> fetch -> parse and returns a DataFrame.

From the command line the same thing is:

```bash
python -m bandcamp_aotd scrape              # incremental
python -m bandcamp_aotd scrape --full       # full backfill
```"""),

    code("""from bandcamp_aotd.extract import scrape_articles

# Raise or remove max_pages for a real run.
df = scrape_articles(max_pages=2)
print(df.shape)
df.head()"""),

    code("""df["parse_status"].value_counts()"""),

    md("""## Next

`02_spotify_enrichment.ipynb` attaches Spotify catalog metadata — cover art,
release dates and links — to what was scraped here."""),
]


# ═══════════════════════════════════════════════════════════════════════════
# 02 - Spotify enrichment
# ═══════════════════════════════════════════════════════════════════════════
NB_02 = [
    md("""# 02 - Spotify Enrichment

**Input:** scraped articles
**Output:** the same rows plus `spotify_*` columns
**Cost:** one API call per row, plus one per *unique* artist

Bandcamp's own pages give text: artist, album, label, genre, location. What
they don't give is cover art, a canonical release date, or a link anyone can
click. Spotify does, and matching the two gives the dashboard and the web app
something that looks like a product rather than a table.

### Why Client Credentials

Only public catalog data is used (`/search` and `/albums`), so this
authenticates with the **Client Credentials flow** — no user login, no scopes,
no redirect URI. One-time setup:

```bash
pip install -r requirements.txt
cp .env.example .env     # then fill in SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET
```

Credentials come from <https://developer.spotify.com/dashboard>."""),

    code(BOOTSTRAP),

    md("""## 1. Load the data to enrich"""),

    code("""import pandas as pd
from bandcamp_aotd import config

df = pd.read_csv(config.ENRICHED_CSV)
print(df.shape)
df.head(3)"""),

    md("""## 2. Test on a handful of rows first

Always. This confirms the credentials work and that matching behaves before
spending two thousand API calls finding out it doesn't."""),

    code("""from bandcamp_aotd.enrich import SpotifyClient

client = SpotifyClient()

sample = df.head(5)
sample_results = client.enrich_dataframe(sample, artist_col="Artist", album_col="Album")

pd.concat([
    sample[["Artist", "Album"]].reset_index(drop=True),
    sample_results[["spotify_match_status", "spotify_match_artist",
                    "spotify_match_album", "spotify_release_date"]].reset_index(drop=True),
], axis=1)"""),

    md("""## 3. Run the full album pass

Three things make a 2,300-row run survivable:

**Checkpointing.** Progress is written to CSV every 50 rows. If the kernel
dies, just re-run the cell — completed rows are skipped and previously-errored
rows are retried. Nothing is paid for twice.

**Per-row error capture.** An individual failure lands in
`spotify_match_status` instead of raising, so one weird compilation doesn't
end the run.

**Run-level abort on a hard rate limit.** This one was learned the hard way.
An earlier version of this pipeline paced at ~10 requests/second and Spotify
answered with `Retry-After: 86109` — a 24-hour cooldown. Because the per-row
handler treated it as an ordinary error, it burned through the remaining 1,592
rows in seconds, marked every one of them failed, and poisoned the checkpoint
with work that was never attempted.

A long rate limit is a *run-level* condition, not a row-level one. It now
raises `SpotifyRateLimitError`, which is deliberately not caught per row: the
run stops, the checkpoint is flushed first, and re-running after the cooldown
resumes from exactly the right place. The default pacing is also gentler
(~3 requests/second), which finishes the full dataset in about 13 minutes
without tripping the limit at all."""),

    code("""from bandcamp_aotd.enrich import SpotifyRateLimitError

try:
    spotify_results = client.enrich_dataframe(
        df,
        artist_col="Artist",
        album_col="Album",
        checkpoint_path=str(config.SPOTIFY_ALBUM_CHECKPOINT),
    )
except SpotifyRateLimitError as exc:
    print(f"Stopped early: {exc}")
    print("Progress is checkpointed - re-run this cell after the cooldown.")
    raise

spotify_results["spotify_match_status"].value_counts()"""),

    md("""## 4. Merge and save"""),

    code("""enriched = pd.concat(
    [df.reset_index(drop=True), spotify_results.reset_index(drop=True)], axis=1
)
enriched.to_csv(config.ENRICHED_CSV, index=False)
print(f"Match rate: {enriched['spotify_match_status'].eq('matched').mean():.1%}")
enriched.head(3)"""),

    md("""## 5. Enrich artists

One call per **unique** artist rather than per row. `enrich_artists` dedups
automatically, which matters less than it sounds here (most artists appear
once) but costs nothing and makes the pass cheaper as the archive grows.

This adds the artist photo and profile link — the two fields the artist
endpoint provides that aren't already on the album object."""),

    code("""artist_results = client.enrich_artists(
    enriched["spotify_artist_id"],
    checkpoint_path=str(config.SPOTIFY_ARTIST_CHECKPOINT),
)
artist_results["spotify_artist_status"].value_counts()"""),

    code("""enriched = enriched.merge(
    artist_results, left_on="spotify_artist_id", right_index=True, how="left"
)
enriched.to_csv(config.ENRICHED_CSV, index=False)
enriched.head(3)"""),

    md("""## Notes on trusting this data

- **Filter on status before trusting any `spotify_*` column.**
  `spotify_match_status` and `spotify_artist_status` are each `matched`,
  `no_match` / `no_id`, or `error: ...`.

- **Spot-check for false positives.** Spotify's search relevance and Bandcamp's
  naming don't always agree, especially for compilations and split releases.
  Compare `spotify_match_artist` against `Artist` on a sample.

- **A `no_match` is a finding, not a gap.** Plenty of Bandcamp Daily picks
  simply aren't on Spotify — that's part of what makes Bandcamp Bandcamp. The
  unmatched rate is worth reporting, not hiding.

- **Deliberately omitted:** `Album.genres`, `Album.label`, `Album.popularity`
  and the artist equivalents are deprecated in Spotify's current API and come
  back empty or unreliable. The Bandcamp `genre_tag` and `record_label` columns
  are the better source and are already in the dataset."""),
]


# ═══════════════════════════════════════════════════════════════════════════
# 03 - Cleaning and geography
# ═══════════════════════════════════════════════════════════════════════════
NB_03 = [
    md("""# 03 - Data Cleaning and Geography

**Input:** scraped + enriched articles
**Output:** the analytics table -> `data/processed/aotd_analytics.csv`

This is where the messiest column in the dataset gets fixed.

`label_location_raw` is free text that a label owner typed into their own
Bandcamp profile. Across ~2,300 articles it contains every failure mode you'd
expect and several you wouldn't. Left alone it produces **422 distinct
"locations"** — many of which are the same place spelled differently — and it
is unusable for a map.

After cleaning: **407 distinct locations, 82 countries, and zero unresolved
values.**"""),

    code(BOOTSTRAP),

    code("""import pandas as pd
from bandcamp_aotd import config
from bandcamp_aotd.legacy import load_legacy_csv

df = load_legacy_csv(config.ENRICHED_CSV)
print(f"{df['label_location_raw'].nunique()} distinct raw location strings")
df["label_location_raw"].dropna().sample(10, random_state=7).tolist()"""),

    md("""## The problems, and the order they have to be fixed in

The cleaner is an explicit nine-step pipeline in
`src/bandcamp_aotd/transform/locations.py`. **Order is load-bearing**, and two
steps in particular have to happen when they do:

| # | Step | Fixes |
|---|---|---|
| 1 | `fix_whitespace` | `"Osaka ,  Japan"` -> `"Osaka, Japan"` |
| 2 | `fix_cjk` | CJK placenames -> romanised |
| 3 | `fix_dc` | six spellings of Washington D.C. -> one |
| 4 | `fix_turkish_dotted_i` | U+0130 -> plain I |
| 5 | `fix_case` | title-case everything |
| 6 | `fix_title_artifacts` | repair what `.title()` broke |
| 7 | `expand_uk` | `"Uk"` -> `"United Kingdom"` |
| 8 | `expand_bare_cities` | `"Chicago"` -> `"Chicago, Illinois"` |
| 9 | `apply_aliases` | typos, translations, accent duplicates |

**Step 4 before step 5.** The Turkish dotted capital İ (U+0130) does not
survive `str.title()` — Python decomposes it into `I` plus a combining dot,
which then defeats every later string comparison and silently splits
`İstanbul` into two separate cities. Normalising it *first* is the only
reliable fix.

**Steps 8 and 9 after step 5.** Both are dictionary lookups. Their keys are
written in title case, so casing has to be settled before they run or nothing
matches."""),

    code("""from bandcamp_aotd.transform import locations as loc

examples = [
    "Osaka , Japan",
    "LONDON, UK",
    "Washington, D.C., D.C.",
    "İstanbul, Turkey",
    "Chicago",
    "Bogota, Colombia",
    "Kzn, South Africa",
]
pd.DataFrame({
    "raw": examples,
    "cleaned": [loc.clean_location(x) for x in examples],
})"""),

    md("""### Watching one value move through every step

Worth running when adding a new rule — it makes an ordering mistake obvious
immediately."""),

    code("""value = "  İSTANBUL ,  turkey  "
print(f"{'input':<24} {value!r}")
for step in loc.CLEANING_STEPS:
    value = step(value)
    print(f"{step.__name__:<24} {value!r}")"""),

    md("""## Splitting into city / state / country

A cleaned string still isn't mappable — a choropleth needs a country column.
`split_location` handles the shapes that actually occur in the data:

- Countries whose own name contains a comma (São Tomé and Príncipe) are
  matched **first**, before any comma splitting can tear them apart.
- A single token is resolved by lookup: country, US state, Canadian province,
  or an unqualified city.
- UK constituent countries (England, Scotland, Wales, Northern Ireland) are
  returned as the **country**, not as a region under "United Kingdom" — that's
  how they appear standalone in the source data and how mapping tools expect
  them.

Country names come from `pycountry`, plus a hand-maintained alias map. The
alias map isn't redundant: ISO 3166 stores Turkey as "Türkiye", Czech Republic
as "Czechia" and Ivory Coast as "Côte d'Ivoire", none of which is what a label
owner types or what a dashboard reader wants to see."""),

    code("""cases = [
    "Brooklyn, New York",
    "Berlin, Germany",
    "Toronto, Ontario",
    "England, United Kingdom",
    "São Tomé, São Tomé and Príncipe",
    "Japan",
]
pd.DataFrame(
    [loc.split_location(c) for c in cases],
    columns=["city", "state", "country"],
    index=cases,
)"""),

    md("""## Build the full analytics table

`build_analytics_table` runs every transformation stage in order: text
normalisation, calendar features, geography, the independent-artist flag, the
deterministic `article_id`, de-duplication, and finally the canonical column
set.

One row gets rejected here — an article with no publication date. The grain of
the warehouse is "one published article", so a row without a date isn't a fact,
it's a parse failure. It's dropped loudly rather than allowed to sit in the
dashboard as a null-dated feature."""),

    code("""from bandcamp_aotd.transform import build_analytics_table

analytics = build_analytics_table(df)
print(analytics.shape)
analytics.head(3)"""),

    md("""## Verify the cleaning actually worked

Three checks worth running every time the rules change."""),

    code("""raw_unique = df["label_location_raw"].nunique()
clean_unique = analytics["location_clean"].nunique()
unresolved = (analytics["location_clean"].notna() & analytics["country"].isna()).sum()

print(f"Raw distinct locations   : {raw_unique}")
print(f"Cleaned distinct locations: {clean_unique}  ({raw_unique - clean_unique} duplicates collapsed)")
print(f"Distinct countries        : {analytics['country'].nunique()}")
print(f"Unresolved (no country)   : {unresolved}   <- must be 0")
print(f"Location coverage         : {analytics['country'].notna().mean():.1%}")"""),

    md("""### Any location that still can't be resolved

This should print nothing. When it doesn't, the value goes into `ALIASES` or
`CITY_EXPANSIONS` in `locations.py` and gets a test case in
`tests/test_locations.py`."""),

    code("""missing = analytics.loc[
    analytics["location_clean"].notna() & analytics["country"].isna(),
    "location_clean",
].value_counts()
print(missing if len(missing) else "All locations resolved to a country.")"""),

    md("""## Save and load

The CSV is the portable copy — the repo clones and runs with no credentials.
Postgres is the source of truth for the dashboard and the app.

```bash
python -m bandcamp_aotd transform
python -m bandcamp_aotd load
```"""),

    code("""from bandcamp_aotd.load import write_csv

write_csv(analytics)"""),

    md("""## Next

`04_exploratory_analysis.ipynb` looks at what's actually in the archive."""),
]


# ═══════════════════════════════════════════════════════════════════════════
# 04 - EDA
# ═══════════════════════════════════════════════════════════════════════════
NB_04 = [
    md("""# 04 - Exploratory Analysis

**Question:** What has Bandcamp Daily actually covered in fifteen years, and
how has that changed?

This notebook profiles the archive before any hypothesis gets tested — shape,
coverage, quality, and the handful of distributions that shape every later
question."""),

    code(BOOTSTRAP),

    code("""import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from bandcamp_aotd import config

sns.set_theme(style="whitegrid")
PALETTE = ["#629aa9", "#e07a5f", "#3d5a80", "#81b29a", "#f2cc8f"]
ACCENT = PALETTE[0]

df = pd.read_csv(config.ANALYTICS_CSV, parse_dates=["published_date"])
print(f"{len(df):,} articles | {df['published_date'].min():%b %Y} - {df['published_date'].max():%b %Y}")
df.head(3)"""),

    md("""## Data quality first

Before any chart: how complete is each column, and which gaps are real
missingness versus a pipeline problem?"""),

    code("""quality = pd.DataFrame({
    "non_null": df.notna().sum(),
    "null_pct": (df.isna().mean() * 100).round(1),
    "distinct": df.nunique(),
})
quality.sort_values("null_pct", ascending=False).head(15)"""),

    md("""Three gaps are worth naming explicitly, because a reader will ask:

- **`article_url` is empty for historic rows.** The archive was originally
  exported before URLs were captured. That's exactly why the warehouse keys on
  a content hash rather than the URL — see
  `src/bandcamp_aotd/transform/identity.py`.
- **About a fifth of features have no Spotify match.** Partly genuine (many
  Bandcamp picks aren't on Spotify at all — which is rather the point of
  Bandcamp), partly title mismatches. Treat the match rate as a lower bound on
  availability.
- **~3.5% of rows have no location.** The label never filled in the field.
  Nothing to recover; just report it."""),

    md("""## Publication cadence

"Album of the Day" implies one per day. It isn't, quite — and the shape of the
gap says something about how the section has been run."""),

    code("""by_year = df.groupby(df["published_date"].dt.year).size()

fig, ax = plt.subplots(figsize=(11, 4.5))
ax.bar(by_year.index, by_year.values, color=ACCENT, width=0.75)
ax.set_title("Album of the Day features per year", fontsize=13, pad=12)
ax.set_ylabel("Features")
ax.set_xlabel("")
ax.spines[["top", "right"]].set_visible(False)
for year, value in by_year.items():
    ax.text(year, value + 3, str(value), ha="center", fontsize=8, color="#555")
plt.tight_layout()
plt.show()"""),

    code("""dow = (df["published_date"].dt.day_name()
       .value_counts()
       .reindex(["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]))

fig, ax = plt.subplots(figsize=(9, 4))
colors = [ACCENT if d not in ("Saturday", "Sunday") else "#c9d6d9" for d in dow.index]
ax.bar(dow.index, dow.values, color=colors, width=0.7)
ax.set_title("Features by day of week", fontsize=13, pad=12)
ax.set_ylabel("Features")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()"""),

    md("""## Genre mix

25 genre tags cover the whole archive, and the distribution is heavily skewed
— which is worth knowing before running any per-genre statistic."""),

    code("""genre = df["genre_tag"].value_counts()

fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(genre.index[::-1], genre.values[::-1], color=ACCENT, height=0.7)
ax.set_title("Features by genre tag", fontsize=13, pad=12)
ax.set_xlabel("Features")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()

print(f"Top 5 genres account for {genre.head(5).sum() / genre.sum():.1%} of all features")"""),

    md("""### Genre share over time

Counts hide the interesting movement; share doesn't."""),

    code("""top_genres = genre.head(8).index
trend = (
    df[df["genre_tag"].isin(top_genres)]
    .groupby([df["published_date"].dt.year, "genre_tag"])
    .size()
    .unstack(fill_value=0)
)
share = trend.div(trend.sum(axis=1), axis=0)

fig, ax = plt.subplots(figsize=(12, 5.5))
share.plot(kind="area", stacked=True, ax=ax, colormap="Spectral", alpha=0.9, linewidth=0)
ax.set_title("Genre share of Album of the Day, by year (top 8 tags)", fontsize=13, pad=12)
ax.set_ylabel("Share of features")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
ax.legend(title="Genre", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
ax.margins(x=0)
plt.tight_layout()
plt.show()"""),

    md("""## Independent vs. signed

The single most striking number in the dataset."""),

    code("""indie_overall = df["is_independent"].mean()
indie_by_year = df.groupby(df["published_date"].dt.year)["is_independent"].mean()

fig, ax = plt.subplots(figsize=(11, 4.5))
ax.plot(indie_by_year.index, indie_by_year.values, marker="o",
        color=ACCENT, linewidth=2, markersize=5)
ax.axhline(indie_overall, color="#e07a5f", linestyle="--", linewidth=1.4,
           label=f"All-time average ({indie_overall:.0%})")
ax.set_title("Share of features that are self-released", fontsize=13, pad=12)
ax.set_ylabel("Independent share")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
ax.set_ylim(0, 1)
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()

print(f"{indie_overall:.1%} of all Album of the Day features are self-released.")"""),

    md("""## Geography

54% of everything featured comes from the United States. Whether that's a bias
or simply reflects where Bandcamp's userbase is, is the question notebook 06
takes up."""),

    code("""country = df["country"].value_counts().head(15)

fig, ax = plt.subplots(figsize=(9, 6.5))
ax.barh(country.index[::-1], country.values[::-1], color=ACCENT, height=0.7)
ax.set_title("Features by label country (top 15)", fontsize=13, pad=12)
ax.set_xlabel("Features")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()

concentration = country.head(3).sum() / df["country"].notna().sum()
print(f"Top 3 countries account for {concentration:.1%} of all located features")"""),

    md("""## Contributors

343 writers have contributed, but the distribution has a very long tail —
which is what makes notebook 05's author analysis restrict itself to the top
15. Comparing a writer with four reviews against one with 110 isn't a
comparison, it's noise."""),

    code("""authors = df["author"].value_counts()

print(f"{len(authors)} distinct contributors")
print(f"Median reviews per contributor: {authors.median():.0f}")
print(f"Top 15 contributors wrote {authors.head(15).sum() / len(df):.1%} of all features")

fig, ax = plt.subplots(figsize=(9, 6))
top15 = authors.head(15)
ax.barh(top15.index[::-1], top15.values[::-1], color=ACCENT, height=0.7)
ax.set_title("Most prolific contributors", fontsize=13, pad=12)
ax.set_xlabel("Reviews")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()"""),

    md("""## What this opens up

| Question | Notebook |
|---|---|
| Do individual writers have measurable genre and geography biases? | `05_editorial_bias_analysis.ipynb` |
| Are certain cities specialised in specific sounds? | `06_geographic_hubs.ipynb` |"""),
]


# ═══════════════════════════════════════════════════════════════════════════
# 05 - Editorial bias
# ═══════════════════════════════════════════════════════════════════════════
NB_05 = [
    md("""# 05 - Editorial Bias Analysis

**Question:** Do individual Bandcamp Daily writers have measurable, systematic
preferences — or does the section's coverage look like one editorial voice?

This matters commercially, not just as trivia. Editorial coverage is
discovery: if a handful of writers each reliably champion a specific sound or
scene, then *which writer gets assigned* materially affects which artists get
surfaced. That is exactly the question a music company's editorial or curation
team asks about its own playlist editors.

### A note on the word "bias"

Used here in the statistical sense — a systematic deviation from the site
average — not as an accusation. A specialist writer covering the genre they
know best is a feature of good editorial, not a flaw. What follows measures
the effect; interpreting it is a separate judgement.

### Scope

Restricted to the **top 15 contributors by review count**. Comparing a writer
with four reviews against one with 110 produces noise, not insight."""),

    code(BOOTSTRAP),

    code("""import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns
from scipy.stats import chi2_contingency, entropy as scipy_entropy

from bandcamp_aotd import config

sns.set_theme(style="whitegrid")
ACCENT = "#629aa9"

df = pd.read_csv(config.ANALYTICS_CSV, parse_dates=["published_date"])

TOP_N = 15
top_authors = df["author"].value_counts().head(TOP_N).index
df_top = df[df["author"].isin(top_authors)].copy()

print(f"{len(df_top):,} reviews by the top {TOP_N} contributors "
      f"({len(df_top) / len(df):.0%} of the archive)")
df["author"].value_counts().head(TOP_N)"""),

    md("""## 1. Genre concentration

Row-normalised, so each row is one writer's genre mix as a percentage of their
own output. Reading down a column shows which writers over-index on a genre;
reading across a row shows how spread out a writer is."""),

    code("""genre_counts = df_top.groupby(["author", "genre_tag"]).size().unstack(fill_value=0)
genre_norm = genre_counts.div(genre_counts.sum(axis=1), axis=0)

# Order writers by how concentrated they are — most specialised at the top.
order = genre_norm.max(axis=1).sort_values(ascending=False).index
genre_norm = genre_norm.loc[order]

fig, ax = plt.subplots(figsize=(17, 7))
sns.heatmap(
    genre_norm,
    cmap=sns.light_palette(ACCENT, as_cmap=True),
    annot=True, fmt=".0%", annot_kws={"fontsize": 7},
    linewidths=0.5, linecolor="white",
    cbar_kws={"label": "Share of that writer's reviews"},
    ax=ax,
)
ax.set_title("Genre mix per contributor (row-normalised, most specialised first)",
             fontsize=13, pad=14)
ax.set_xlabel("")
ax.set_ylabel("")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()"""),

    md("""## 2. Is the difference statistically significant?

The heatmap shows differences exist. A chi-square goodness-of-fit test asks
whether they're larger than sampling noise would produce — comparing each
writer's genre distribution against the archive-wide distribution.

**Caveats, stated up front:**

- Fifteen tests are run without a multiple-comparison correction. Bonferroni
  at α=0.05 would demand p < 0.0033; the raw p-values are shown so both
  thresholds can be read off.
- Chi-square assumes expected cell counts of roughly 5 or more. With 25 genre
  tags and some writers having under 40 reviews, sparse cells make individual
  p-values approximate. The test is used to *rank* writers by deviation, not
  to make a precise claim about any single one."""),

    code("""overall_genre = df["genre_tag"].value_counts()

results = []
for author in top_authors:
    author_genre = df_top.loc[df_top["author"] == author, "genre_tag"].value_counts()
    combined = pd.DataFrame({"author": author_genre, "overall": overall_genre}).fillna(0)
    if len(combined) > 1:
        chi2, p, dof, _ = chi2_contingency(combined.T)
        results.append({
            "Author": author,
            "Reviews": int(overall_genre.index.size and df["author"].value_counts()[author]),
            "chi2": round(chi2, 1),
            "p_value": p,
            "p<0.05": p < 0.05,
            "p<0.0033 (Bonferroni)": p < 0.05 / TOP_N,
        })

chi_df = pd.DataFrame(results).sort_values("p_value").reset_index(drop=True)
chi_df["p_value"] = chi_df["p_value"].map(lambda v: f"{v:.2e}")
chi_df"""),

    md("""## 3. Diversity, measured properly

A count of distinct genres is a bad diversity measure: a writer with 14 genres
where 90% of reviews sit in one of them is not diverse. Shannon entropy
weights by how evenly the reviews are spread.

Read in bits. 0 = every review in one genre. Higher = more evenly spread. The
theoretical maximum across 25 tags is log₂(25) ≈ 4.6 bits."""),

    code("""def shannon_bits(series):
    return scipy_entropy(series.value_counts(normalize=True), base=2)

scores = (
    df_top.groupby("author")
    .agg(
        genre_entropy=("genre_tag", shannon_bits),
        geo_entropy=("country", shannon_bits),
        reviews=("album", "count"),
    )
    .reset_index()
)

fig, axes = plt.subplots(1, 2, figsize=(15, 6))
for ax, (col, title, color) in zip(axes, [
    ("genre_entropy", "Genre diversity", ACCENT),
    ("geo_entropy", "Geographic diversity", "#e07a5f"),
]):
    ordered = scores.sort_values(col)
    ax.barh(ordered["author"], ordered[col], color=color, height=0.65)
    ax.set_title(f"{title} (Shannon entropy)", fontsize=12, pad=10)
    ax.set_xlabel("Bits — higher is more diverse")
    ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()

scores.sort_values("genre_entropy", ascending=False).round(2)"""),

    md("""## 4. Independent-artist preference

Some writers consistently cover self-released records; others gravitate to
label releases. The red line is the site-wide average, so distance from it is
the effect size."""),

    code("""indie = df_top.groupby("author")["is_independent"].mean().sort_values()
baseline = df["is_independent"].mean()

fig, ax = plt.subplots(figsize=(10, 6.5))
colors = ["#e07a5f" if v < baseline else ACCENT for v in indie.values]
ax.barh(indie.index, indie.values, color=colors, height=0.65)
ax.axvline(baseline, color="#3d3d3d", linestyle="--", linewidth=1.5,
           label=f"Site average ({baseline:.0%})")
ax.set_title("Share of each contributor's reviews that are self-released",
             fontsize=13, pad=12)
ax.set_xlabel("Independent share")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()"""),

    md("""## 5. Geographic focus"""),

    code("""top_countries = df["country"].value_counts().head(8).index
geo = (
    df_top[df_top["country"].isin(top_countries)]
    .groupby(["author", "country"])
    .size()
    .unstack(fill_value=0)
)
geo_share = geo.div(df_top.groupby("author").size(), axis=0).fillna(0)
geo_share = geo_share.loc[geo_share.sum(axis=1).sort_values(ascending=False).index]

fig, ax = plt.subplots(figsize=(13, 6))
geo_share.plot(kind="bar", stacked=True, ax=ax, colormap="Spectral", width=0.75)
ax.set_title("Country mix per contributor (top 8 countries)", fontsize=13, pad=12)
ax.set_ylabel("Share of that writer's reviews")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
ax.legend(title="Country", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()"""),

    md("""## 6. Label affinity

For signed releases only: does a writer keep returning to the same label?
Concentration is the share of that writer's signed reviews going to their most
covered label."""),

    code("""signed = df_top[~df_top["is_independent"]].copy()

rows = []
for author in top_authors:
    labels = signed.loc[signed["author"] == author, "record_label"].dropna()
    if len(labels) < 5:
        continue
    counts = labels.value_counts()
    rows.append({
        "Author": author,
        "Top label": counts.idxmax(),
        "Reviews of that label": int(counts.max()),
        "Total signed reviews": len(labels),
        "Concentration": round(counts.max() / len(labels), 3),
    })

pd.DataFrame(rows).sort_values("Concentration", ascending=False).reset_index(drop=True)"""),

    md("""## 7. Who was writing when

Contributor turnover is its own explanation for shifts in coverage: a genre
can appear to decline simply because the writer who covered it stopped
contributing. Worth checking before attributing any trend to editorial
strategy."""),

    code("""activity = (
    df_top.groupby("author")["published_date"]
    .agg(first="min", last="max", reviews="count")
    .sort_values("first")
    .reset_index()
)

fig, ax = plt.subplots(figsize=(12, 6.5))
for i, row in activity.iterrows():
    ax.barh(
        y=i,
        width=(row["last"] - row["first"]).days,
        left=mdates.date2num(row["first"]),
        height=0.55, color=ACCENT, alpha=0.85,
    )
    ax.text(mdates.date2num(row["last"]) + 25, i, str(int(row["reviews"])),
            va="center", fontsize=8, color="#555")

ax.set_yticks(range(len(activity)))
ax.set_yticklabels(activity["author"])
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_title("Contributor activity windows (label = total reviews)", fontsize=13, pad=12)
ax.spines[["top", "right"]].set_visible(False)
fig.autofmt_xdate()
plt.tight_layout()
plt.show()"""),

    md("""## What this establishes

Writers at Bandcamp Daily are measurably specialised — in genre, in geography,
and in their appetite for self-released work. The chi-square results say those
differences are larger than chance for most of the top contributors, and the
entropy scores put a number on how concentrated each writer is.

**What it does not establish.** This is observational data with no assignment
mechanism visible. A writer's genre concentration could reflect their own
taste, an editor assigning them to their specialism, or the mix of what was
submitted while they happened to be active. Separating those would need the
assignment data, which isn't public.

The honest framing for a stakeholder: *coverage is concentrated by writer, and
here is how much* — not *writers are biased*."""),
]


# ═══════════════════════════════════════════════════════════════════════════
# 06 - Geographic hubs
# ═══════════════════════════════════════════════════════════════════════════
NB_06 = [
    md("""# 06 - Global Indie Hubs

**Question:** Are certain cities specialised in specific sounds — and is the
answer still the one everybody assumes?

Bristol and trip-hop, Detroit and techno, Nashville and country: music writing
runs on these associations. This dataset can test them, because every article
carries the record label's self-reported location.

**What's being measured, precisely:** the label's location, not the artist's.
Those diverge — an artist in Lagos signed to a Berlin label registers as
Berlin. That makes this a map of *where the infrastructure is*, which is
arguably the more interesting question, but it is not a map of where musicians
live. Worth stating before anyone reads a conclusion off it."""),

    code(BOOTSTRAP),

    code("""import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from bandcamp_aotd import config

sns.set_theme(style="whitegrid")
ACCENT = "#629aa9"

df = pd.read_csv(config.ANALYTICS_CSV, parse_dates=["published_date"])
located = df[df["country"].notna()].copy()

print(f"{len(located):,} of {len(df):,} features have a resolved location "
      f"({len(located) / len(df):.1%})")
print(f"{located['country'].nunique()} countries | {located['city'].nunique()} cities")"""),

    md("""## 1. The global picture

Concentration first, because it frames everything else."""),

    code("""country_counts = located["country"].value_counts()
share = country_counts / country_counts.sum()

fig, ax = plt.subplots(figsize=(10, 6.5))
top = country_counts.head(15)
ax.barh(top.index[::-1], top.values[::-1], color=ACCENT, height=0.7)
ax.set_title("Album of the Day features by label country (top 15)", fontsize=13, pad=12)
ax.set_xlabel("Features")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()

print(f"United States : {share.iloc[0]:.1%}")
print(f"Top 3         : {share.head(3).sum():.1%}")
print(f"Top 10        : {share.head(10).sum():.1%}")
print(f"\\nThe remaining {len(country_counts) - 10} countries share "
      f"{1 - share.head(10).sum():.1%} of all coverage.")"""),

    md("""### Has that concentration changed over time?

A section that broadened its geographic reach would show a falling US share.
This is the more useful version of the previous chart — a single number moving
over fifteen years, rather than a static ranking."""),

    code("""us_share = (
    located.assign(is_us=located["country"].eq("United States"))
    .groupby(located["published_date"].dt.year)["is_us"]
    .agg(["mean", "size"])
)
us_share = us_share[us_share["size"] >= 20]      # drop thin years

fig, ax = plt.subplots(figsize=(11, 4.5))
ax.plot(us_share.index, us_share["mean"], marker="o", color=ACCENT,
        linewidth=2, markersize=5)
ax.axhline(share.iloc[0], color="#e07a5f", linestyle="--", linewidth=1.4,
           label=f"All-time US share ({share.iloc[0]:.0%})")
ax.set_title("US share of Album of the Day features, by year", fontsize=13, pad=12)
ax.set_ylabel("US share")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
ax.set_ylim(0, 1)
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()

us_share.round(3)"""),

    md("""### Was 2024 a change of writers?

The share sat between 53% and 61% from 2018 to 2023, then fell 12 points in a
single year. A step like that invites the obvious explanation: different
people started writing. If so, writers active both before and after 2024
should look the same as they always did, and the drop should come from
newcomers. Test it directly."""),

    code("""from scipy.stats import chi2_contingency

before = located[located["year"].between(2018, 2023)]
after = located[located["year"] >= 2024]
continuing = set(before["author"].dropna()) & set(after["author"].dropna())

since_2024 = df[df["year"] >= 2024]
print(f"{since_2024['author'].isin(continuing).mean():.0%} of features since 2024 "
      f"were written by the {len(continuing)} writers also active in 2018-23")

b = before[before["author"].isin(continuing)]["country"].eq("United States")
a = after[after["author"].isin(continuing)]["country"].eq("United States")
newcomers = after[~after["author"].isin(continuing)]["country"].eq("United States")

print(f"Continuing writers, US share 2018-23: {b.mean():.1%}  (n={len(b)})")
print(f"Continuing writers, US share 2024+:   {a.mean():.1%}  (n={len(a)})")
print(f"Newer writers,      US share 2024+:   {newcomers.mean():.1%}  (n={len(newcomers)})")

table = [[b.sum(), (~b).sum()], [a.sum(), (~a).sum()]]
chi2, p, _, _ = chi2_contingency(table)
print(f"\\nChi-square, continuing writers before vs after: chi2={chi2:.2f}, p={p:.3f}")"""),

    md("""The same writers moved. Their US share fell by about eight points, and the
change is unlikely to be noise; newer writers sit at a similar level. The
shift happened *within* the existing roster, which points to commissioning or
submissions rather than personnel. The timing coincides with Bandcamp's sale
to Songtradr in late 2023, but observational data can't establish cause."""),

    md("""## 2. Which cities are specialised?

**Lift** is the metric: a genre's share *within* a city divided by that
genre's share across the whole archive.

- lift = 1 → the city looks exactly like the archive average
- lift = 5 → that genre is five times as prevalent there as everywhere else

Lift is badly behaved in the tail. A city with 12 features and one children's
record scores a lift of 66 and tops any unfiltered ranking, which means
nothing at all. Two floors keep it honest: **the city needs ≥ 10 features, and
the city/genre pair needs ≥ 3.** Raw counts are kept alongside the ratio so
the evidence is visible rather than taken on trust.

This is the same calculation as the `vw_city_genre_specialisation` view in
`db/views.sql` — defined once in SQL, reproduced here for the narrative."""),

    code("""MIN_CITY_FEATURES = 10
MIN_PAIR_FEATURES = 3

city_totals = located.groupby("city").size()
eligible = city_totals[city_totals >= MIN_CITY_FEATURES].index
global_share = located["genre_tag"].value_counts(normalize=True)

pairs = (
    located[located["city"].isin(eligible)]
    .groupby(["city", "country", "genre_tag"])
    .size()
    .reset_index(name="features")
)
pairs = pairs[pairs["features"] >= MIN_PAIR_FEATURES]
pairs["city_features"] = pairs["city"].map(city_totals)
pairs["city_share"] = pairs["features"] / pairs["city_features"]
pairs["global_share"] = pairs["genre_tag"].map(global_share)
pairs["lift"] = (pairs["city_share"] / pairs["global_share"]).round(2)

print(f"{len(eligible)} cities clear the {MIN_CITY_FEATURES}-feature floor")
pairs.sort_values("lift", ascending=False).head(15).reset_index(drop=True)"""),

    code("""top_pairs = pairs.sort_values("lift", ascending=False).head(12)
labels = top_pairs["city"] + " — " + top_pairs["genre_tag"]

fig, ax = plt.subplots(figsize=(10, 6.5))
bars = ax.barh(labels[::-1], top_pairs["lift"][::-1], color=ACCENT, height=0.7)
ax.axvline(1, color="#3d3d3d", linestyle="--", linewidth=1.3,
           label="Archive average (lift = 1)")
for bar, n in zip(bars, top_pairs["features"][::-1]):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f"n={n}", va="center", fontsize=8, color="#666")
ax.set_title("Most genre-specialised cities (lift vs. archive average)",
             fontsize=13, pad=12)
ax.set_xlabel("Lift")
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()"""),

    md("""### Testing the received wisdom directly

The clichés, checked against the data rather than assumed."""),

    code("""CLAIMS = [
    ("Bristol", "Electronic"),
    ("Detroit", "Electronic"),
    ("Detroit", "Hip-Hop/Rap"),
    ("Nashville", "Country"),
    ("Berlin", "Electronic"),
    ("Chicago", "Hip-Hop/Rap"),
    ("Tokyo", "Ambient"),
]

rows = []
for city, genre in CLAIMS:
    subset = located[located["city"] == city]
    if subset.empty:
        rows.append({"City": city, "Genre": genre, "Verdict": "no data"})
        continue
    n = int((subset["genre_tag"] == genre).sum())
    city_share = n / len(subset)
    lift = city_share / global_share.get(genre, float("nan"))
    rows.append({
        "City": city,
        "Genre": genre,
        "City features": len(subset),
        f"{genre} features": n,
        "City share": f"{city_share:.0%}",
        "Lift": round(lift, 2),
        "Verdict": ("supported" if lift >= 2 and n >= 3
                    else "weak" if lift >= 1.2 and n >= 3
                    else "not supported"),
    })

pd.DataFrame(rows)"""),

    md("""## 3. Independent share by country

Where do self-released records get featured most? Restricted to countries with
enough features for the proportion to mean anything."""),

    code("""by_country = (
    located.groupby("country")
    .agg(features=("article_id", "size"), indie_share=("is_independent", "mean"))
    .query("features >= 20")
    .sort_values("indie_share")
)

fig, ax = plt.subplots(figsize=(10, 6))
baseline = located["is_independent"].mean()
colors = ["#e07a5f" if v < baseline else ACCENT for v in by_country["indie_share"]]
ax.barh(by_country.index, by_country["indie_share"], color=colors, height=0.68)
ax.axvline(baseline, color="#3d3d3d", linestyle="--", linewidth=1.4,
           label=f"Global average ({baseline:.0%})")
for i, (features, sharev) in enumerate(zip(by_country["features"], by_country["indie_share"])):
    ax.text(sharev + 0.015, i, f"n={features}", va="center", fontsize=8, color="#666")
ax.set_title("Self-released share by country (≥20 features)", fontsize=13, pad=12)
ax.set_xlabel("Independent share")
ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.show()"""),

    md("""## 4. The choropleth aggregate

Tableau and the web app draw the map from `vw_coverage_by_country`. This
recomputes the same aggregate in pandas as a cross-check that the view and the
analysis agree. It deliberately writes nothing: the file Tableau reads,
`data/exports/coverage_by_country.csv`, has one producer
(`python -m bandcamp_aotd export --views`), so it always matches the view."""),

    code("""choropleth = (
    located.groupby("country")
    .agg(
        features=("article_id", "size"),
        distinct_artists=("artist", "nunique"),
        distinct_labels=("record_label", "nunique"),
        distinct_genres=("genre_tag", "nunique"),
        indie_share=("is_independent", "mean"),
        first_feature=("published_date", "min"),
        latest_feature=("published_date", "max"),
    )
    .reset_index()
    .sort_values("features", ascending=False)
)
choropleth["pct_of_all_features"] = (choropleth["features"] / choropleth["features"].sum() * 100).round(2)

print(f"{len(choropleth)} countries")
choropleth.head(10)"""),

    md("""## Findings

**Coverage is heavily concentrated.** Over half of everything Bandcamp Daily
features comes from US-based labels, and the top three countries account for
roughly three quarters. Whether that reflects editorial preference or simply
where Bandcamp's label base sits cannot be settled from this data alone — it
would need Bandcamp's own catalogue as a denominator, which isn't public.

**City specialisation is real but narrower than the clichés suggest.** A
handful of city/genre pairs clear a meaningful lift threshold with enough
features to be credible. Many of the famous associations don't survive the
count floor — not because they're false, but because the archive simply
doesn't contain enough features from those cities to say.

**The measurement caveat is the finding, partly.** Label location is a proxy
for artist location, and a lossy one. Any conclusion here is about where the
*infrastructure* of independent music sits, not where the musicians are.

### Where this goes next

- **Geocode `dim_place`** (the `latitude` / `longitude` columns already exist)
  to move from country choropleth to city-level point mapping.
- **Add artist location** — Bandcamp artist pages carry it — and measure the
  label-to-artist distance directly. Do labels sign locally, or is independent
  music genuinely borderless? That's the question this dataset is closest to
  answering and doesn't yet."""),
]


NOTEBOOK_FILES = {
    "01_data_collection.ipynb": NB_01,
    "02_spotify_enrichment.ipynb": NB_02,
    "03_data_cleaning_and_geography.ipynb": NB_03,
    "04_exploratory_analysis.ipynb": NB_04,
    "05_editorial_bias_analysis.ipynb": NB_05,
    "06_geographic_hubs.ipynb": NB_06,
}


def main() -> None:
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    for name, cells in NOTEBOOK_FILES.items():
        path = NOTEBOOKS / name
        prefix = name.split("_")[0]
        path.write_text(
            json.dumps(notebook(_with_ids(cells, prefix)), indent=1, ensure_ascii=False)
        )
        n_md = sum(1 for c in cells if c["cell_type"] == "markdown")
        n_code = len(cells) - n_md
        print(f"{name:<42} {len(cells):>2} cells ({n_md} markdown, {n_code} code)")


if __name__ == "__main__":
    main()

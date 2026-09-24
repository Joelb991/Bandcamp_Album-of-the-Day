# Bandcamp *Album of the Day* — Editorial Analytics

An end-to-end analytics project on fifteen years of music criticism: a
production-shaped ELT pipeline, a modelled Postgres warehouse, and an analysis
of how editorial attention is actually distributed across genres, geographies
and writers.

**2,287 articles · 2011–2026 · 80 countries · 343 contributors · 585 labels**

---

## The question

Bandcamp Daily has published an *Album of the Day* almost every weekday since
2011. It is one of the more influential discovery channels in independent
music — a feature there measurably moves sales for an artist nobody has heard
of.

Nobody publishes what that coverage looks like in aggregate. So:

> **Where does editorial attention actually go — and is it distributed the way
> the industry assumes?**

Three sub-questions the pipeline was built to answer:

1. **Geography** — how concentrated is coverage by country and city, and has it
   broadened over fifteen years?
2. **Editorial** — do individual writers have measurable, systematic genre and
   geography preferences?
3. **Structure** — how much of what gets featured is self-released versus
   label-backed, and is that changing?

## Headline findings

| Finding | Number |
|---|---|
| Features from US-based labels | **54.3%** |
| Features from the top 3 countries combined | **73.5%** |
| Features that are **self-released** | **66.2%** |
| Share of all coverage written by the top 15 contributors | **29.5%** |
| Most genre-specialised city (Pittsburgh / Metal) | **16× the archive average** |

Coverage is far more concentrated than "global independent music" suggests —
geographically, and in who writes it. The full analysis, with the caveats that
matter, is in [`docs/findings.md`](docs/findings.md).

---

## Architecture

```
  Bandcamp Daily                Spotify Web API
  (HTML, no API)                (Client Credentials)
        │                              │
        ▼                              ▼
  ┌───────────┐   ┌──────────┐   ┌───────────┐   ┌────────┐
  │  EXTRACT  │──▶│ TRANSFORM│──▶│  ENRICH   │──▶│  LOAD  │
  │ discover  │   │ locations│   │  albums   │   │ upsert │
  │ fetch     │   │ calendar │   │  artists  │   │ dims + │
  │ parse     │   │ identity │   │           │   │ fact   │
  └───────────┘   └──────────┘   └───────────┘   └────┬───┘
   HTML cache      article_id      checkpointed       │
                   (SHA-1 key)     + resumable        ▼
                                              ┌───────────────┐
                                              │   POSTGRES    │
                                              │  (Supabase)   │
                                              │ fact_article  │
                                              │ dim_place     │
                                              │ dim_author    │
                                              │ dim_label     │
                                              │ pipeline_run  │
                                              └───────┬───────┘
                                                      │  6 analytics views
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                              Tableau           Next.js app        Notebooks
                              dashboard         (Vercel)           (analysis)
```

Every consumer reads the **same views**, so a metric is defined once. Change
the definition of "indie share" in `db/views.sql` and the dashboard, the app
and the notebooks all move together.

### Three decisions worth explaining

**The warehouse keys on a content hash, not the URL.** Historic rows came from
a CSV export with no article URL; fresh scrapes have one. Keying on the URL
would load the same article twice. `article_id` is a SHA-1 over the normalised
publication date, artist and album — deterministic across both sources, which
is what makes `INSERT … ON CONFLICT DO UPDATE` safe to re-run over an
overlapping date range. See
[`transform/identity.py`](src/bandcamp_aotd/transform/identity.py).

**Every fetched page is cached to disk.** Regexes against scraped HTML will
need fixing. Without a cache, each fix means re-crawling 2,300 pages; with one,
re-parsing the archive takes seconds, runs offline, and holds the footprint on
Bandcamp to exactly one request per article ever.

**The scrape is incremental by construction.** The index is newest-first, so a
refresh reads until it recognises a full page of articles it already has, then
stops. A weekly refresh costs one HTTP request instead of five hundred.

---

## Quick start

```bash
git clone https://github.com/Joelb991/Bandcamp_Album-of-the-Day.git
cd Bandcamp_Album-of-the-Day

python -m venv .venv && source .venv/bin/activate
pip install -e ".[db,analysis,dev]"

cp .env.example .env        # add Spotify + Supabase credentials
```

**No credentials?** The processed dataset is committed, so the analysis
notebooks (03–06) run immediately on a fresh clone:

```bash
jupyter lab notebooks/04_exploratory_analysis.ipynb
```

### Running the pipeline

```bash
make init-db        # apply schema.sql + views.sql to Postgres
make backfill       # load the historic 2,287-row dataset
make refresh        # scrape new articles → enrich → transform → load
make export         # write the Tableau extract
make test           # run the test suite
```

Or step by step:

```bash
python -m bandcamp_aotd scrape --max-pages 3   # crawl new articles
python -m bandcamp_aotd enrich                 # attach Spotify metadata
python -m bandcamp_aotd transform              # build the analytics table
python -m bandcamp_aotd load                   # upsert into Postgres
```

Every stage runs standalone, because when something breaks you want to re-run
one step, not all of them.

### Keeping it current

Bandcamp publishes ~5 new features a week. A weekly refresh is enough:

```cron
0 6 * * 1  cd /path/to/repo && .venv/bin/python -m bandcamp_aotd refresh
```

Each run writes a row to `pipeline_run`, and `vw_pipeline_health` exposes
freshness and match rates for the dashboard's "data as of" badge.

---

## Repository layout

```
├── src/bandcamp_aotd/       # the pipeline package
│   ├── config.py            #   paths + credentials, resolved once
│   ├── cli.py               #   command line interface
│   ├── extract/             #   discover → fetch → parse
│   ├── enrich/              #   Spotify Web API client
│   ├── transform/           #   locations, calendar, identity, text
│   ├── load/                #   Postgres upsert + CSV/Tableau exports
│   └── legacy.py            #   bridge from the original CSV exports
├── db/
│   ├── schema.sql           # tables, indexes, constraints, audit trail
│   └── views.sql            # the semantic layer (6 analytics views)
├── notebooks/               # 01 collection → 06 geographic hubs
├── tests/                   # 60 tests: parsing, cleaning, identity, transforms
├── tools/build_notebooks.py # notebooks generated from reviewable Python
├── data/
│   ├── raw/                 # original exports + HTML cache (git-ignored)
│   └── processed/           # the analytics table (committed)
├── dashboards/tableau/      # Tableau workbook
├── app/                     # Next.js web app (planned — see docs/roadmap.md)
└── docs/                    # architecture, data dictionary, findings, roadmap
```

## Notebooks

| # | Notebook | What it covers |
|---|---|---|
| 01 | [Data collection](notebooks/01_data_collection.ipynb) | Crawling the archive politely and incrementally |
| 02 | [Spotify enrichment](notebooks/02_spotify_enrichment.ipynb) | Catalog matching, checkpointing, rate-limit handling |
| 03 | [Cleaning & geography](notebooks/03_data_cleaning_and_geography.ipynb) | 422 messy location strings → 80 countries |
| 04 | [Exploratory analysis](notebooks/04_exploratory_analysis.ipynb) | Cadence, genre mix, indie share, contributors |
| 05 | [Editorial bias analysis](notebooks/05_editorial_bias_analysis.ipynb) | Chi-square, Shannon entropy, label affinity |
| 06 | [Global indie hubs](notebooks/06_geographic_hubs.ipynb) | City/genre lift — testing the received wisdom |

Notebooks import from `src/` rather than defining logic inline, so the
scheduled pipeline and the analysis run identical code.

---

## Engineering notes

**Tested.** 60 tests cover the HTML parsers, the nine-step location cleaner,
the identity hash and the transform pipeline. Every location test case is a
real value from the dataset that broke something.

```bash
pytest -q
```

**Idempotent.** Loading the same data twice inserts 2,287 rows and then updates
2,287 rows — verified against a live Postgres, not assumed.

**Honest about its own failures.** Two bugs found while building this are
documented rather than quietly fixed: a batched-insert bug that silently
returned only the last batch's surrogate keys, and a Spotify rate-limit
handler that treated a 24-hour ban as a per-row error and burned through 1,592
rows marking them all failed. Both are described in
[`docs/architecture.md`](docs/architecture.md).

**Known limitation.** The Spotify match rate currently sits at 23% because
that enrichment run was interrupted by the rate limit above. Re-running
`python -m bandcamp_aotd enrich` resumes from the checkpoint. The pacing is now
gentler by default (~3 req/s), which completes the full dataset in about 13
minutes.

---

## Tech stack

**Python** (pandas, requests) · **PostgreSQL / Supabase** · **SQL**
(window functions, CTEs, `ON CONFLICT` upserts) · **Tableau** ·
**pytest** · **Spotify Web API**

## Data & ethics

Bandcamp Daily is scraped politely: one request per article ever (cached
thereafter), sub-1-req/s pacing, a real User-Agent, and `Retry-After` honoured.
Only public editorial pages are read — no user data, no paywalled content, no
audio. Spotify is accessed through its documented public API under the Client
Credentials flow.

The dataset is editorial metadata about published articles. It supports claims
about *what was covered*; it does not support claims about anyone's intent.

## License

MIT — see [LICENSE](LICENSE).

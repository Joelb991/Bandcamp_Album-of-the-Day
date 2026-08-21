# Roadmap — the presentation layer

The pipeline and warehouse are done. What remains is the part a hiring manager
actually clicks on.

---

## The recommendation, up front

**Build both, but make them do different jobs.** Two views of the same data is
redundant and looks it. Two *products* with different audiences is a portfolio.

| | Tableau dashboard | Next.js app on Vercel |
|---|---|---|
| **Audience** | A hiring manager for a BI / analytics role | A hiring manager for a data / product role, and anyone who likes music |
| **Job it does** | "Can this person model data and build a decision tool?" | "Can this person ship something people use?" |
| **Content** | The **analysis** — coverage concentration, editorial specialisation, city lift | The **archive** — a browsable, searchable index of every Album of the Day |
| **Reads from** | `vw_coverage_by_country`, `vw_author_profile`, `vw_city_genre_specialisation`, `vw_genre_trend` | `vw_latest_features`, `vw_article`, `vw_pipeline_health` |
| **Effort** | ~1 weekend | ~2 weekends |

The split matters because they answer different interview questions. The
dashboard proves the analysis; the app proves you can build.

**If you only build one: build the Tableau dashboard first.** Tableau Public
gives a free, shareable link that goes straight on a résumé, and the roles you
named (Sony Music, Sony Pictures, Chrome Hearts BI) list Tableau or Power BI in
their requirements far more often than they list React. The app is the
differentiator once the dashboard exists.

> **On Tableau vs. Power BI:** you already have the `.twb` started, and
> Tableau Public publishes to a public URL for free. Power BI's free tier has
> no public-share equivalent — you'd be reduced to screenshots or a PDF, which
> is a materially worse portfolio artifact. If a specific employer is a
> Microsoft shop, rebuild the same thing in Power BI later; the semantic layer
> in `db/views.sql` means it's a connection change, not a rebuild.

---

## Tableau dashboard

### Connection

Connect **live to Supabase Postgres** (`Connect > PostgreSQL`) rather than to a
CSV. Live connection means "this refreshes automatically" is a true statement
you can make in an interview, and the views do the aggregation server-side.

Keep `make export` as a fallback — `data/exports/tableau_aotd_extract.csv` —
for offline demos and for Tableau Public, which cannot reach a private
database. Publishing to Tableau Public requires an extract.

### Proposed layout — three tabs

**Tab 1 — Coverage** *(the headline)*

- KPI row: total features · countries · % self-released · latest article date
  (from `vw_pipeline_health`, so the dashboard states its own freshness)
- Choropleth by country, coloured on `features` — from `vw_coverage_by_country`
- **US share over time**, as a line. This is the single strongest chart in the
  project: a clear 17-point decline since 2017. Lead with it.
- Genre share streamgraph by year — from `vw_genre_trend`

**Tab 2 — Editorial**

- Contributor scatter: reviews (x) vs. genre entropy (y), sized by distinct
  countries. Specialists sit bottom-right, generalists top-right — the shape
  tells the story without a caption.
- Genre-mix heatmap for the top 15 contributors, row-normalised
- Indie share by contributor, with the site-average reference line

**Tab 3 — Scenes**

- City/genre lift, from `vw_city_genre_specialisation`, with the count floors
  already applied in SQL
- **Show `features` alongside `lift` on every mark.** A lift of 20 backed by
  three records should look weak on the page, not impressive. This is the
  single most important design decision in the dashboard — it is what
  separates a chart that informs from one that misleads.

### Design notes

- One accent colour (`#629aa9` is used throughout the notebooks), grey for
  everything else. Colour should mean something.
- Every sheet gets a one-line takeaway as its title — *"US share of coverage
  has fallen 17 points since 2017"*, not *"US Share by Year"*. A title that
  states the finding is worth more than a title that names the axes.
- Filters: year range, genre, country, independent/signed. No more.
- Put the caveat about label-vs-artist location in a visible footnote on the
  Coverage tab. Stating a limitation on the page reads as rigour, not weakness.

---

## Next.js app on Vercel

### Why this one is worth building

A dashboard shows you can analyse. An app that lets someone type "Detroit" and
get every Detroit record Bandcamp has ever featured shows you can turn analysis
into something usable — and it is genuinely fun, which matters when the person
reviewing it works at a music company.

### Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Next.js 14, App Router | Server components query Postgres directly — no separate API layer to build |
| Hosting | Vercel | Free tier, git-push deploys |
| Data | Supabase Postgres via `@supabase/supabase-js` | Already the warehouse; row-level security off, read-only anon key |
| Styling | Tailwind + shadcn/ui | Fast, and stops the app looking like a school project |
| Charts | Recharts | Adequate for two or three charts; don't rebuild Tableau here |

### Scope — four routes

```
/                     Browsable archive: cover art grid, newest first,
                      filter by genre / country / year, full-text search.
                      Powered by vw_latest_features and vw_article.

/article/[id]         One feature: cover, artist, album, label, location,
                      genre, author, link to the Bandcamp article and the
                      Spotify album.

/map                  Country choropleth + city list. Click a country,
                      see its features. This is the analysis, made
                      interactive — the one thing the app does that
                      Tableau can't do as well.

/about                What the data is, how it's collected, and the
                      limitations. Links to the GitHub repo and the
                      Tableau dashboard.
```

Every page footer shows *"Data as of {date}"* from `vw_pipeline_health`. It is
three lines of code and it signals that the thing is live rather than a
snapshot.

### Do this before building the app

**Finish the Spotify enrichment.** The app is carried entirely by cover art —
a grid where 77% of tiles are placeholders looks broken, not sparse. One
`python -m bandcamp_aotd enrich` run at the new pacing (~13 minutes) fixes it.
This is the highest-value item on this whole page.

### Suggested build order

1. `.env.local` with the Supabase anon key; confirm a server component can read
   `vw_latest_features`
2. `/` with the grid and no filters — deploy it. A deployed ugly version beats
   a perfect local one.
3. Filters and search
4. `/article/[id]`
5. `/map`
6. `/about`, then polish

---

## Backlog, ranked by value per unit of effort

### 1. Complete the Spotify enrichment — *1 hour, mostly waiting*
Unblocks the app's cover art and makes "what fraction of independent music is
even on Spotify?" answerable. Highest value item here.

### 2. Deploy the Tableau dashboard to Tableau Public — *1 weekend*
Produces a public URL for the résumé. Do this before the app.

### 3. Add artist location — *1 weekend*
Bandcamp artist pages carry it. This converts the project's central caveat into
a measurable quantity — label-to-artist distance — and answers the question the
dataset is closest to but cannot currently reach: *do labels sign locally?*
The most intellectually interesting extension available.

### 4. Geocode `dim_place` — *2 hours*
`latitude` / `longitude` already exist in the schema. Nominatim via `geopy`,
one call per *place* (407) not per row, cached. Turns the country choropleth
into city-level points.

### 5. Ship the Next.js app — *2 weekends*
Scope above.

### 6. Schedule the refresh — *30 minutes*
GitHub Actions on a weekly cron running `python -m bandcamp_aotd refresh`,
with `DATABASE_URL` and the Spotify credentials as repository secrets. The
pipeline is already built for this; it just needs the trigger. A green weekly
badge on the README is disproportionately convincing.

### 7. Data quality dashboard — *half a day*
`pipeline_run` and `vw_pipeline_health` already collect what's needed. A small
page showing load history, match rates and freshness. Optional, but it is the
kind of thing that makes a data-engineering interviewer sit up.

---

## What to say about this project in an interview

The pipeline is the strongest part and it is the part that will be least
visible from a screenshot. Three things worth having ready:

**On the idempotent load.** "The warehouse keys on a content hash rather than
the article URL, because historic rows came from an export that predates URL
capture. That's what makes the upsert safe to re-run over an overlapping date
range." This is a real data-engineering problem with a real solution.

**On the bugs.** The batched-insert bug in
[`architecture.md`](architecture.md) is a good story: it produced plausible
wrong numbers rather than an error, it would have failed silently months later
when a dimension crossed 1,000 rows, and it was caught by testing against a real
database rather than by reading the code. Being able to describe a bug you
found in your own work is worth more than a project with no bugs described.

**On the caveats.** Knowing that label location is not artist location — and
saying so before being asked — is the difference between an analyst and someone
who makes charts.

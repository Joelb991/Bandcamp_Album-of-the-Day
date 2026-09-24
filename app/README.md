# Web app

A Next.js app on Vercel that reads the same Supabase warehouse as the Tableau
dashboard and the notebooks. Four pages:

| Route | Reads from | What it does |
|---|---|---|
| `/` | `vw_article`, `vw_author_profile`, `vw_city_genre_specialisation`, `vw_coverage_by_country`, `vw_latest_features` | The four headline findings, each with an interactive chart and a table view |
| `/archive` | `vw_article` | Every feature, searchable and filterable client-side; filter state lives in the URL |
| `/map` | `vw_coverage_by_country`, `vw_article` | Choropleth by label country; click a country for its genres, cities and latest features |
| `/methodology` | `vw_pipeline_health` | Pipeline, semantic layer, live data-quality numbers and caveats |

Every page footer shows "data as of" from `vw_pipeline_health`.

## How it works

- **Server components query the views directly** (`src/lib/queries.ts`) with
  [`postgres`](https://github.com/porsager/postgres). There is no API layer,
  and nothing reads the base tables, so a metric is defined once in
  [`db/views.sql`](../db/views.sql) for every surface.
- **Static generation with daily revalidation.** Pages are built once and
  regenerated at most once a day. If the database is unreachable during a
  regeneration, Next.js keeps serving the last good page, so a paused
  free-tier Supabase project can't take the site down.
- **A daily Vercel Cron** (`vercel.json` → `/api/cron/refresh`) runs one
  query, which keeps Supabase from pausing after a quiet week, and marks the
  pages stale so the next visit picks up new data.
- **The map is projected at build time** (`src/lib/geo.ts`, d3-geo), so the
  browser receives SVG paths rather than TopoJSON plus a projection library.
- **Charts are hand-built SVG** (`src/components/charts/`) with hover and
  keyboard tooltips, and every chart has a table-view twin.

## Run locally

```bash
cd app
npm install
cp .env.example .env.local     # add DATABASE_URL
npm run dev                    # http://localhost:3000
```

## Deploy to Vercel

1. **Create a read-only database role** (recommended). The app only ever
   selects from the views, so it shouldn't hold the owner credentials:

   ```bash
   psql "$DATABASE_URL" -v app_password='choose-a-long-password' -f db/app_role.sql
   ```

   The app's connection string is then the **session pooler** URI (port
   **5432**) with the user `aotd_app.<project-ref>` and that password:

   ```
   postgresql://aotd_app.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

   Not the transaction pooler on 6543: `next build` runs 10 workers that
   pipeline queries, and through that pooler pages stall past the 60-second
   limit.

2. **Import the repo** at [vercel.com/new](https://vercel.com/new) and set
   **Root Directory** to `app`. The framework is detected automatically.

3. **Add environment variables** (Project Settings → Environment Variables):

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the read-only connection string from step 1 |
   | `CRON_SECRET` | any long random string (`openssl rand -hex 32`) |
   | `NEXT_PUBLIC_PORTFOLIO_URL` | optional: where the "Built by" footer link points |

4. **Deploy.** Every push to `main` redeploys. If a build can't reach the
   database, the build fails and the previous deployment stays live.

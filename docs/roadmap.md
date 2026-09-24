# Roadmap

## Shipped

| | What | Where |
|---|---|---|
| ✓ | Pipeline: extract → transform → enrich → load, idempotent and resumable | [`src/bandcamp_aotd/`](../src/bandcamp_aotd/) |
| ✓ | Postgres warehouse on Supabase with an audit trail | [`db/schema.sql`](../db/schema.sql) |
| ✓ | Semantic layer: 8 views shared by every surface | [`db/views.sql`](../db/views.sql) |
| ✓ | Spotify enrichment: every row resolved, 79.6% matched | [data dictionary](data_dictionary.md#about-that-20) |
| ✓ | Six analysis notebooks | [`notebooks/`](../notebooks/) |
| ✓ | Tableau dashboard: Coverage, Editorial, Scenes | [Tableau Public](https://public.tableau.com/views/bandcamp_aotd/Coverage) · [`dashboards/`](../dashboards/) |
| ✓ | Web app: findings, searchable archive, interactive map, methodology | [`app/`](../app/) |

The two presentation layers do different jobs on purpose. The Tableau
dashboard is the **analysis**: a BI tool for reading coverage concentration,
writer specialisation and city lift. The web app is the **product**: anyone
can type "Detroit" and get every Detroit record Bandcamp has featured, with the
findings and the map alongside. Both read the same views, so their numbers
agree.

---

## Next, ranked by value per unit of effort

### 1. Schedule the refresh — *30 minutes*

The pipeline is incremental by construction; it only needs a trigger. A
GitHub Actions workflow on a weekly cron running
`python -m bandcamp_aotd refresh`, with `DATABASE_URL` and the Spotify
credentials as repository secrets, keeps the warehouse current. The web app
and the "data as of" footer pick up new rows on their next daily regeneration
with no further change.

### 2. Artist location — *1 weekend*

Bandcamp artist pages carry it. This converts the project's central caveat
(label location is not artist location) into a measurable quantity, the
label-to-artist distance, and answers the question the dataset is closest to
but can't yet reach: *do labels sign locally?*

### 3. Geocode `dim_place` — *2 hours*

`latitude` and `longitude` already exist in the schema. Nominatim via `geopy`,
one call per *place* (407), not per row, cached. That moves the map from
countries to city-level points and makes the city/genre lift visual.

### 4. Separate "not on Spotify" from "not matched" — *half a day*

The 20.4% without a match mixes genuine absence with title mismatches. A fuzzy
second pass would turn 79.6% from a lower bound into an availability rate:
*what fraction of the independent music Bandcamp champions is on the dominant
streaming service at all?*

### 5. A denominator — *open-ended*

Coverage share is only interpretable against what was available to cover.
Even a rough sample of Bandcamp's catalogue by country would turn "54.8% US"
from a description into a claim about editorial preference.

### 6. Data-quality page — *half a day*

`pipeline_run` and `vw_pipeline_health` already collect load history, match
rates and freshness. A small page charting them over time would complete the
monitoring story.

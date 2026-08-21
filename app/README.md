# Web app (planned)

A Next.js app on Vercel that reads the same Supabase warehouse the Tableau
dashboard does — a browsable, searchable archive of every Album of the Day.

Nothing is built here yet. The full scope, stack rationale and build order are
in [`../docs/roadmap.md`](../docs/roadmap.md).

**Before starting:** finish the Spotify enrichment
(`python -m bandcamp_aotd enrich`). The app is carried by cover art, and at the
current 23% match rate the grid would look broken rather than sparse.

## Planned routes

| Route | Reads from | Purpose |
|---|---|---|
| `/` | `vw_latest_features`, `vw_article` | Cover-art grid, newest first, filter + search |
| `/article/[id]` | `vw_article` | One feature, with links out to Bandcamp and Spotify |
| `/map` | `vw_coverage_by_country` | Interactive choropleth |
| `/about` | `vw_pipeline_health` | What the data is, how it's collected, its limits |

# Dashboards

## Tableau

**Published:** [https://public.tableau.com/views/bandcamp_aotd/Coverage](https://public.tableau.com/views/bandcamp_aotd/Coverage)

`tableau/bandcamp_aotd.twbx` — the packaged workbook (data embedded, so it opens
without any connection). Three dashboards: **Coverage**, **Editorial**, **Scenes**.

**Connect it live to Supabase Postgres** (`Connect > PostgreSQL`) and build on
the views in `db/views.sql` rather than on `fact_article` directly, so the
dashboard and the notebooks share one definition of every metric.

For Tableau Public — which cannot reach a private database — use the CSV exports.
There are two, because the flat table and the SQL views come from different places:

```bash
make export                                # data/exports/tableau_aotd_extract.csv (flat article table)
python -m bandcamp_aotd export --views     # author_profile, city_genre_specialisation, coverage_by_country,
                                           # genre_trend, label_leaderboard (from db/views.sql)
```

After re-exporting, refresh every extract in Tableau (Data ▸ Refresh All Extracts) and
republish under the same name so the link above stays the same.

The proposed three-tab layout, the chart-by-chart rationale and the design
notes are in [`../docs/roadmap.md`](../docs/roadmap.md).

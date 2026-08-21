# Dashboards

## Tableau

`tableau/bandcamp_aotd.twb` — the working Tableau workbook.

**Connect it live to Supabase Postgres** (`Connect > PostgreSQL`) and build on
the views in `db/views.sql` rather than on `fact_article` directly, so the
dashboard and the notebooks share one definition of every metric.

For Tableau Public — which cannot reach a private database — use the extract:

```bash
make export        # writes data/exports/tableau_aotd_extract.csv
```

The proposed three-tab layout, the chart-by-chart rationale and the design
notes are in [`../docs/roadmap.md`](../docs/roadmap.md).

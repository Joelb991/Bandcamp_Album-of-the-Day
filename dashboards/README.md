# Dashboards

## Tableau

**Published:** [https://public.tableau.com/views/bandcamp_aotd/Coverage](https://public.tableau.com/views/bandcamp_aotd/Coverage)

`tableau/bandcamp_aotd.twbx` — the packaged workbook (data embedded, so it opens
without any connection). Three dashboards: **Coverage**, **Editorial**, **Scenes**.

### Layout

| Tab | Question | Sheets | Built on |
|---|---|---|---|
| **Coverage** | How concentrated is coverage by country, and is it changing? | KPIs · US share over time · features by label country · self-released share by country · most-featured labels | flat extract, `coverage_by_country`, `label_leaderboard` |
| **Editorial** | Do writers have measurable genre and geography preferences? | KPIs · top-15 share · contributor concentration · genre specialisation (entropy) · genre mix per contributor · appetite for self-released work | flat extract, `author_profile` |
| **Scenes** | Which cities over-index on which genres? | KPIs · strongest scene · city × genre lift · scene map · genre trend over time | `city_genre_specialisation`, `genre_trend` |

### Design decisions

- **Titles state the finding**, not the axes: the US share sheet reads as a
  sentence about what changed, not *"US Share by Year"*.
- **Every tab is sourced and attributed**: a footnote gives the source, the
  author and a not-affiliated note.
- **Shares use located features as the denominator.** The ~3.5% of features
  with no known label location are excluded, not counted as "not US". In a
  calculated field:

  ```
  AVG(IF ISNULL([country]) THEN NULL
      ELSEIF [country] = "United States" THEN 1 ELSE 0 END)
  ```

  This matches the SQL views, the web app and `docs/findings.md`
  (54.8% all-time; 63.1% in 2017 → 44.2% in 2025).

### Refreshing the data

**Connect it live to Supabase Postgres** (`Connect > PostgreSQL`) and build on
the views in `db/views.sql` rather than on `fact_article` directly, so the
dashboard, the web app and the notebooks share one definition of every metric.

For Tableau Public — which cannot reach a private database — use the CSV exports.
There are two, because the flat table and the SQL views come from different places:

```bash
make export                                # data/exports/tableau_aotd_extract.csv (flat article table)
python -m bandcamp_aotd export --views     # author_profile, city_genre_specialisation, coverage_by_country,
                                           # genre_trend, label_leaderboard, pipeline_health (from db/views.sql)
```

After re-exporting, refresh every extract in Tableau (Data ▸ Refresh All Extracts) and
republish under the same name so the link above stays the same.

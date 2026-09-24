# Findings

What fifteen years of Bandcamp Daily's *Album of the Day* looks like in
aggregate — and what the data does and doesn't support.

**Scope:** 2,368 articles, October 2011 – September 2026 (refreshed 2026-09-24). Coverage is continuous from
2016; 2011 contributes 9 articles and is excluded from any time series.

---

## 1. Coverage is concentrated, but it is opening up

More than half of everything featured comes from a US-based label.

| | Share of located features |
|---|---|
| United States | **54.8%** |
| Top 3 countries (US, UK, Canada) | **74.9%** |
| Remaining 77 countries combined | **25.1%** |

The static number undersells the more interesting result. **The US share fell
about 19 points from its 2017 peak to 2025, and most of that fall came in two
years:**

| Year | US share |
|---|---|
| 2017 | **63.1%** (peak) |
| 2019 | 53.3% |
| 2021 | 56.7% |
| 2023 | 61.3% |
| 2024 | 49.1% |
| 2025 | **44.2%** |
| 2026 (to September) | 49.4% |

From 2018 to 2023 the share wandered between 53% and 61% with no clear
direction. Then it broke: down 12 points in 2024 and another 5 in 2025. 2026
so far has come back to 49.4%, so 2025 may turn out to be the low point rather
than a new level, but the 2024 break stands. That is a step change, not drift, and a section that genuinely broadened its
geographic reach rather than one that talks about doing so. Total volume did
not change (~230 features a year since 2017), so international coverage grew
by reallocating attention, not by adding more of it.

**It isn't a change of writers.** 70% of features since 2024 were written by
people already writing for the section in 2018–23, and those same 53 writers'
US share fell from 53.6% to 46.2% (χ² p = 0.02). Writers who joined since sit
at 50.3%, so who was writing doesn't explain the drop. The shift happened *within* the existing roster, which points
to commissioning or submissions rather than personnel. The timing coincides
with Bandcamp's sale to Songtradr in late 2023, after which roughly half the
company's staff were let go, but this dataset can't establish cause.

**The caveat that limits this.** These are *label* locations, not artist
locations. Bandcamp's own catalogue composition is not public, so there is no
denominator: it is impossible to say from this data whether 54% US reflects
editorial preference or simply where Bandcamp's labels are. The trend over time
is the robust part; the level is not.

---

## 2. Two thirds of everything featured is self-released

**66.3%** of Album of the Day features are self-released rather than
label-backed, and that ratio is remarkably stable — between 60% and 71% every
year since 2016, with no trend.

This is the number that most contradicts how music discovery is usually
described. The section's editorial centre of gravity is not small labels; it is
artists with no label at all.

By country, among those with 30+ features, the spread is wide: Canada (74.5%)
and Australia (72.1%) run well above average, while Germany (42.0%) and France
(41.5%) run well below — suggesting genuinely different independent-music
infrastructures rather than different editorial treatment.

**Caveat.** `is_independent` is derived from a rule (artist and credited label
being the same entity), so it also absorbs rows where the label field failed to
parse. 66.3% is a well-founded estimate, not a census.

---

## 3. Writers are measurably specialised

349 contributors have written for the section, but the top 15 account for
**29.0%** of all coverage — so those writers materially shape what gets
surfaced.

Genre concentration, measured as Shannon entropy in bits (0 = every review in
one genre; ~4.6 = perfectly even across 25 tags):

| Contributor | Reviews | Distinct genres | Entropy (bits) |
|---|---|---|---|
| Dash Lewis | 26 | 2 | **0.24** |
| Michael J. West | 27 | 4 | 0.95 |
| Phillip Mlynar | 39 | 5 | 1.20 |
| … | | | |
| John Morrison | 110 | 15 | **3.15** |

The range is the point. Dash Lewis writes in effectively one genre; John
Morrison spans fifteen across twelve countries. Chi-square tests against the
archive-wide genre distribution find significant deviations for all 15 of the
most active writers at p < 0.05, and for 14 of them after a Bonferroni
correction. These are real specialisms, not sampling noise.

Independent-artist appetite varies too, from 41% to 83% across the top
contributors against a 66% baseline.

**What this does and does not mean.** "Bias" here is the statistical sense — a
systematic deviation from the site average. A specialist covering the genre they
know best is good editorial practice, not a flaw.

More importantly, this is observational data with no visible assignment
mechanism. A writer's concentration could reflect their own taste, an editor
assigning them to their specialism, or simply what was being submitted while
they were active. Those cannot be separated without assignment data that isn't
public.

The honest framing for a stakeholder is *coverage is concentrated by writer,
and here is how much* — not *writers are biased*.

---

## 4. City specialisation is real, but narrower than the clichés

Measured as **lift**: a genre's share within a city divided by that genre's
share across the whole archive. Lift of 5 means five times as prevalent there
as everywhere else.

Lift is badly behaved in the tail — a city with 12 features and one children's
record scores 66 and tops any unfiltered ranking. Two floors are applied: the
city needs ≥10 features, the city/genre pair needs ≥3.

| City | Genre | Features | City total | Lift |
|---|---|---|---|---|
| Nashville | Country | 5 | 21 | **27.2** |
| Pittsburgh | Metal | 12 | 15 | **14.0** |
| Austin | Folk | 3 | 15 | 7.2 |
| Tokyo | Ambient | 4 | 16 | 6.7 |
| Detroit | Hip-Hop/Rap | 11 | 25 | 5.5 |
| Toronto | R&B/Soul | 6 | 34 | 5.0 |
| Chicago | Jazz | 27 | 98 | 3.6 |

**Pittsburgh and Chicago are the credible ones.** 12 of Pittsburgh's 15
features are metal, and 27 of Chicago's 98 are jazz — enough volume that the
ratio means something. Nashville/Country has the highest lift in the table and
the thinnest evidence behind it: five records.

**Small bases move fast.** Between May and September 2026, Nashville added two
country features and its lift jumped from 20.8 to 27.2; Pittsburgh added three
features, one of them metal, and fell from 16.2 to 14.0. A pair resting on a
handful of records can swing several points with every new feature, which is
why the evidence counts sit beside every lift.

**What can't be tested.** Some of music writing's most repeated associations
can't be checked here at all. Bristol now has 12 tagged features, just over the
city floor, but trip-hop isn't one of Bandcamp's 25 genre tags, so the
association has no column to show up in. Absence of evidence, stated as such.

---

## 5. Other observations

**Publication cadence is genuinely weekday-only** — Saturday and Sunday
features are negligible — and volume has been flat at ~230/year since 2017. The
section is a stable, deliberately-sized editorial commitment.

**Genre tagging is incomplete.** 13.1% of articles carry no genre tag,
concentrated in the earlier years before Bandcamp tagged systematically. Any
per-genre statistic should exclude these rather than treat them as a category.

**25 genre tags cover everything**, and the top five (Electronic, Alternative,
Experimental, Hip-Hop/Rap, Jazz) account for more than half (56%) of all
tagged features.

---

## What would strengthen this

In rough order of value per unit of effort:

1. **Artist location.** Bandcamp artist pages carry it. Adding it converts the
   central caveat of §1 and §4 into a measurable quantity — the label-to-artist
   distance — and answers the question this dataset is closest to but cannot
   currently reach: *do labels sign locally, or is independent music genuinely
   borderless?*

2. **A denominator.** Coverage share is only interpretable against the
   composition of what was available to cover. Even a rough sample of Bandcamp's
   catalogue by country would turn "54.8% US" from a description into a claim
   about editorial preference.

3. **Separate "not on Spotify" from "not matched".** Enrichment is complete:
   79.4% of features match a Spotify album. The remaining 20.6% mixes genuine
   absence with title mismatches; a fuzzy second pass (or a check against
   Bandcamp's own links) would turn 79.4% from a lower bound into an
   availability rate, which is the number a streaming or catalogue team would
   actually want.

4. **Geocode `dim_place`.** The columns exist. It moves the map from
   country choropleth to city-level points and makes §4 visual.

# Findings

What fifteen years of Bandcamp Daily's *Album of the Day* looks like in
aggregate — and what the data does and doesn't support.

**Scope:** 2,287 articles, October 2011 – May 2026. Coverage is continuous from
2016; 2011 contributes 9 articles and is excluded from any time series.

---

## 1. Coverage is concentrated, but it is opening up

More than half of everything featured comes from a US-based label.

| | Share of located features |
|---|---|
| United States | **54.3%** |
| Top 3 countries (US, UK, Canada) | **73.5%** |
| Remaining 79 countries combined | **~19%** |

The static number undersells the more interesting result. **The US share has
fallen steadily since 2018:**

| Year | US share |
|---|---|
| 2017 | 60.3% |
| 2019 | 50.5% |
| 2022 | 54.5% |
| 2024 | 47.6% |
| 2025 | **43.0%** |
| 2026 (partial) | **41.8%** |

That is roughly a **17-point decline from the 2017 peak** — a section that has
genuinely broadened its geographic reach, not one that talks about doing so.
For anyone building an editorial or curation strategy, this is the finding with
the clearest read-across: international coverage grew without the total volume
changing (~230 features a year since 2017), meaning it was a reallocation of
attention, not an expansion of it.

**The caveat that limits this.** These are *label* locations, not artist
locations. Bandcamp's own catalogue composition is not public, so there is no
denominator: it is impossible to say from this data whether 54% US reflects
editorial preference or simply where Bandcamp's labels are. The trend over time
is the robust part; the level is not.

---

## 2. Two thirds of everything featured is self-released

**66.2%** of Album of the Day features are self-released rather than
label-backed, and that ratio is remarkably stable — between 60% and 71% every
year since 2016, with no trend.

This is the number that most contradicts how music discovery is usually
described. The section's editorial centre of gravity is not small labels; it is
artists with no label at all.

By country, among those with 20+ features, the spread is wide: Canada (74.8%)
and Australia (74.6%) run well above average, while Germany (41.8%) and France
(42.3%) run well below — suggesting genuinely different independent-music
infrastructures rather than different editorial treatment.

**Caveat.** `is_independent` is derived from a rule (artist and credited label
being the same entity), so it also absorbs rows where the label field failed to
parse. 66.2% is a well-founded estimate, not a census.

---

## 3. Writers are measurably specialised

343 contributors have written for the section, but the top 15 account for
**29.5%** of all coverage — so those writers materially shape what gets
surfaced.

Genre concentration, measured as Shannon entropy in bits (0 = every review in
one genre; ~4.6 = perfectly even across 25 tags):

| Contributor | Reviews | Distinct genres | Entropy (bits) |
|---|---|---|---|
| Dash Lewis | 25 | 2 | **0.24** |
| Michael J. West | 26 | 4 | 0.97 |
| Phillip Mlynar | 39 | 5 | 1.20 |
| … | | | |
| John Morrison | 110 | 15 | **3.15** |

The range is the point. Dash Lewis writes in effectively one genre; John
Morrison spans fifteen across fourteen countries. Chi-square tests against the
archive-wide genre distribution return significant deviations for most of the
top 15 — these are real specialisms, not sampling noise.

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
| Nashville | Country | 3 | 19 | **20.8** |
| Pittsburgh | Metal | 11 | 12 | **16.2** |
| Austin | Folk | 3 | 14 | 7.7 |
| Tokyo | Ambient | 4 | 15 | 7.2 |
| Detroit | Hip-Hop/Rap | 11 | 25 | 5.6 |
| Toronto | R&B/Soul | 6 | 33 | 5.0 |
| Chicago | Jazz | 27 | 95 | 3.8 |

**Pittsburgh and Chicago are the credible ones.** 11 of Pittsburgh's 12
features are metal, and 27 of Chicago's 95 are jazz — enough volume that the
ratio means something. Nashville/Country has the highest lift in the table and
the weakest evidence behind it: three records.

**What did *not* survive.** Several of the most repeated associations in music
writing — Bristol and trip-hop chief among them — don't clear the count floor.
Not because they're false, but because the archive simply doesn't contain
enough features from those cities to test. Absence of evidence, stated as such.

---

## 5. Other observations

**Publication cadence is genuinely weekday-only** — Saturday and Sunday
features are negligible — and volume has been flat at ~230/year since 2017. The
section is a stable, deliberately-sized editorial commitment.

**Genre tagging is incomplete.** 13.6% of articles carry no genre tag,
concentrated in the earlier years before Bandcamp tagged systematically. Any
per-genre statistic should exclude these rather than treat them as a category.

**25 genre tags cover everything**, and the top five (Electronic, Alternative,
Experimental, Hip-Hop/Rap, Jazz) account for roughly half of all tagged
features.

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
   catalogue by country would turn "54% US" from a description into a claim
   about editorial preference.

3. **Complete the Spotify enrichment.** At 527 confirmed matches the
   availability rate is not reportable. A full pass makes "what fraction of
   independent music Bandcamp features is even on Spotify?" answerable — a
   question a streaming or catalogue team would find directly useful.

4. **Geocode `dim_place`.** The columns exist. It moves the map from
   country choropleth to city-level points and makes §4 visual.

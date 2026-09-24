import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Card, Container, PageHeader } from "@/components/ui";
import { CheckIcon } from "@/components/icons";
import { fmtDate, fmtInt, fmtPct } from "@/lib/format";
import { REPO_URL, TABLEAU_URL, repoFile } from "@/lib/links";
import { getHealth, getHeadline } from "@/lib/queries";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "Methodology",
  description: "How the Bandcamp Album of the Day pipeline, warehouse and semantic layer are built, and the limits of the data.",
};

const STAGES = [
  {
    name: "Extract",
    path: "src/bandcamp_aotd/extract",
    body: "Walks Bandcamp Daily's index newest-first and stops at the first page it already has. Every page is cached to disk, so a parser fix re-runs offline instead of re-crawling.",
  },
  {
    name: "Transform",
    path: "src/bandcamp_aotd/transform",
    body: "A nine-step cleaner turns free-text label locations into {places} places across {countries} countries, with none left unresolved. Calendar fields are derived, and each article gets a SHA-1 content-hash key.",
  },
  {
    name: "Enrich",
    path: "src/bandcamp_aotd/enrich",
    body: "Matches each album on the Spotify Web API. Checkpointed and resumable, with a per-run call budget and Retry-After handling after a 24-hour rate-limit ban.",
  },
  {
    name: "Load",
    path: "src/bandcamp_aotd/load",
    body: "INSERT … ON CONFLICT DO UPDATE into Postgres on Supabase, so re-running over overlapping dates updates rows instead of duplicating them. Every run writes an audit row.",
  },
];

const VIEWS = [
  ["vw_article", "Denormalised base view every other view builds on", "all"],
  ["vw_coverage_by_country", "Features, artists, labels and self-released share per country", "map, Tableau"],
  ["vw_city_genre_specialisation", "City × genre lift, with evidence floors applied in SQL", "overview, Tableau"],
  ["vw_author_profile", "Per-writer volume, range and Shannon entropy of genres", "overview, Tableau"],
  ["vw_genre_trend", "Genre share and rank by year", "Tableau, notebooks"],
  ["vw_label_leaderboard", "Labels the editors return to", "Tableau"],
  ["vw_latest_features", "The 100 most recent features", "overview"],
  ["vw_pipeline_health", "Freshness, match rates and last run status", "this page, footer"],
];

const LIFT_SQL = `-- vw_city_genre_specialisation (select list trimmed)
WITH city_totals AS (
    SELECT city, state, country, COUNT(*) AS city_features
    FROM vw_article
    WHERE city IS NOT NULL AND genre_tag IS NOT NULL
    GROUP BY city, state, country
    HAVING COUNT(*) >= 10                    -- evidence floor #1
),
genre_totals AS (
    SELECT genre_tag,
           COUNT(*)::numeric / SUM(COUNT(*)) OVER () AS global_share
    FROM vw_article
    WHERE genre_tag IS NOT NULL
    GROUP BY genre_tag
),
city_genre AS (
    SELECT city, state, country, genre_tag, COUNT(*) AS features
    FROM vw_article
    WHERE city IS NOT NULL AND genre_tag IS NOT NULL
    GROUP BY city, state, country, genre_tag
)
SELECT cg.city, cg.genre_tag, cg.features, ct.city_features,
       ROUND((cg.features::numeric / ct.city_features)
             / NULLIF(gt.global_share, 0), 2) AS lift
FROM city_genre cg
JOIN city_totals ct
  ON  ct.city = cg.city
  AND ct.state   IS NOT DISTINCT FROM cg.state   -- Portland, OR ≠ Portland, ME
  AND ct.country IS NOT DISTINCT FROM cg.country
JOIN genre_totals gt ON gt.genre_tag = cg.genre_tag
WHERE cg.features >= 3;                      -- evidence floor #2`;

function H2({ children }: { children: ReactNode }) {
  return <h2 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{children}</h2>;
}

function Section({ title, intro, children }: { title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <section className="border-t border-line py-12 sm:py-16">
      <Container>
        <H2>{title}</H2>
        {intro && <div className="mt-3 max-w-3xl text-[15px] leading-relaxed text-ink-2">{intro}</div>}
        <div className="mt-8">{children}</div>
      </Container>
    </section>
  );
}

export default async function Methodology() {
  const [health, h] = await Promise.all([getHealth(), getHeadline()]);
  const ok = health.lastRunStatus === "success";

  return (
    <>
      <PageHeader eyebrow="Methodology" title="One pipeline, one warehouse, one set of metric definitions">
        <p>
          A Python ELT pipeline scrapes Bandcamp Daily, enriches it with Spotify and loads a modelled Postgres warehouse. A layer of
          SQL views defines every metric once, and this site, the Tableau dashboard and the analysis notebooks all read from it.
        </p>
      </PageHeader>

      {/* ── Pipeline ─────────────────────────────────────── */}
      <Section title="The pipeline">
        <ol className="grid gap-3 md:grid-cols-4">
          {STAGES.map((s, i) => (
            <li key={s.name} className="relative rounded-xl border border-line bg-surface p-5">
              <p className="text-xs text-muted tnum">0{i + 1}</p>
              <h3 className="mt-1 font-semibold text-ink">{s.name}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-2">
                {s.body.replace("{places}", fmtInt(h.places)).replace("{countries}", fmtInt(h.countries))}
              </p>
              <a href={`${REPO_URL}/tree/main/${s.path}`} target="_blank" rel="noreferrer" className="mt-3 inline-block font-mono text-[11px] text-accent hover:underline">
                {s.path.replace("src/bandcamp_aotd/", "")}/
              </a>
              {i < STAGES.length - 1 && (
                <span aria-hidden="true" className="absolute -right-2.5 top-1/2 z-10 hidden -translate-y-1/2 text-muted md:block">
                  →
                </span>
              )}
            </li>
          ))}
        </ol>

        <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_1.2fr]">
          <div className="rounded-xl border border-line bg-surface p-5">
            <p className="text-xs text-muted">Warehouse · Postgres on Supabase</p>
            <p className="mt-2 font-mono text-[13px] leading-6 text-ink-2">
              <span className="text-ink">fact_article</span> <span className="text-muted">(1 row per feature)</span>
              <br />
              dim_place · dim_author · dim_label
              <br />
              pipeline_run <span className="text-muted">(audit trail)</span>
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface p-5">
            <p className="text-xs text-muted">Semantic layer</p>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">
              <span className="font-semibold text-ink">8 SQL views</span> in{" "}
              <a href={repoFile("db/views.sql")} target="_blank" rel="noreferrer" className="font-mono text-[13px] text-accent hover:underline">
                db/views.sql
              </a>
              . Change a definition there and every surface moves together.
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface p-5">
            <p className="text-xs text-muted">Consumers</p>
            <ul className="mt-2 space-y-1 text-sm text-ink-2">
              <li>
                <span className="text-ink">This site</span>: Next.js on Vercel
              </li>
              <li>
                <a href={TABLEAU_URL} target="_blank" rel="noreferrer" className="text-ink hover:text-accent">
                  Tableau Public
                </a>
                : Coverage, Editorial and Scenes dashboards
              </li>
              <li>
                <a href={`${REPO_URL}/tree/main/notebooks`} target="_blank" rel="noreferrer" className="text-ink hover:text-accent">
                  Six notebooks
                </a>
                : collection through statistical analysis
              </li>
            </ul>
          </div>
        </div>
      </Section>

      {/* ── Health ───────────────────────────────────────── */}
      <Section
        title="Data quality, live"
        intro={
          <p>
            Read from <code className="font-mono text-[13px] text-ink">vw_pipeline_health</code> when this page was generated. Every
            pipeline run writes a row to <code className="font-mono text-[13px] text-ink">pipeline_run</code>, so a failed load leaves
            a record instead of disappearing.
          </p>
        }
      >
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {[
            ["Articles in warehouse", fmtInt(health.totalArticles)],
            ["Spotify match rate", fmtPct(health.spotifyMatchRate)],
            ["Location coverage", fmtPct(health.locationCoverageRate)],
            ["Genre-tagged", fmtPct(100 - h.untaggedShare)],
            ["Latest article", fmtDate(health.latestArticleDate)],
            ["Last load", fmtDate(health.lastLoadAt)],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-line bg-surface px-4 py-3.5">
              <p className="text-xs text-muted">{k}</p>
              <p className="mt-1 text-lg font-semibold tracking-tight text-ink">{v}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 inline-flex items-center gap-2 text-sm text-ink-2">
          <span
            className="inline-flex h-5 w-5 items-center justify-center rounded-full"
            style={{ background: ok ? "var(--good)" : "var(--critical)" }}
          >
            {ok ? <CheckIcon className="h-3 w-3 text-white" /> : <span className="text-xs font-bold text-white">!</span>}
          </span>
          Last pipeline run: <span className="font-medium text-ink">{health.lastRunStatus ?? "unknown"}</span>
        </p>
      </Section>

      {/* ── Semantic layer ───────────────────────────────── */}
      <Section
        title="The semantic layer"
        intro={
          <p>
            No surface queries the base tables. Each metric (indie share, lift, genre entropy) is defined once in SQL, which is what
            keeps the numbers on this site, in Tableau and in the notebooks in agreement.
          </p>
        }
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="overflow-hidden rounded-xl border border-line">
            <table className="w-full border-collapse text-left text-sm">
              <caption className="sr-only">Analytics views</caption>
              <thead className="bg-surface-2 text-xs text-muted">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">View</th>
                  <th scope="col" className="px-3 py-2 font-medium">What it answers</th>
                </tr>
              </thead>
              <tbody>
                {VIEWS.map(([v, d, used]) => (
                  <tr key={v} className="border-t border-line align-top">
                    <td className="px-3 py-2 font-mono text-[12px] text-ink">{v}</td>
                    <td className="px-3 py-2 text-ink-2">
                      {d}
                      <span className="mt-0.5 block text-xs text-muted">Used by: {used}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <pre className="overflow-x-auto rounded-xl border border-line bg-surface p-4 font-mono text-[12px] leading-5 text-ink-2">
              <code>{LIFT_SQL}</code>
            </pre>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              Lift is noisy in the tail: a city with 12 features and one children&apos;s record scores 66 and tops any unfiltered
              ranking. The floors live in the view, and the raw counts stay in the output so a reader can judge the evidence.{" "}
              <a href={repoFile("db/views.sql")} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                Full SQL →
              </a>
            </p>
          </div>
        </div>
      </Section>

      {/* ── Decisions ────────────────────────────────────── */}
      <Section title="Three decisions worth explaining">
        <div className="grid gap-3 md:grid-cols-3">
          <Card>
            <h3 className="font-semibold text-ink">A content hash, not the URL, is the key</h3>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">
              Historic rows came from an export with no article URL; fresh scrapes have one. Keying on the URL would load the same
              article twice. <code className="font-mono text-[12px]">article_id</code> is a SHA-1 of the normalised date, artist and
              album, which is deterministic across both sources and makes the upsert safe to re-run.
            </p>
          </Card>
          <Card>
            <h3 className="font-semibold text-ink">Every fetched page is cached</h3>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">
              Regexes against scraped HTML will need fixing. Without a cache, each fix means re-crawling 2,300 pages; with one,
              re-parsing takes seconds, runs offline, and keeps the footprint on Bandcamp to one request per article, ever.
            </p>
          </Card>
          <Card>
            <h3 className="font-semibold text-ink">Bugs are documented, not buried</h3>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">
              A batched insert silently returned only the last batch&apos;s surrogate keys: plausible wrong numbers, no error. A
              rate-limit handler treated a 24-hour ban as a per-row failure. Both are written up in{" "}
              <a href={repoFile("docs/architecture.md")} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                architecture.md
              </a>
              .
            </p>
          </Card>
        </div>
      </Section>

      {/* ── This site ────────────────────────────────────── */}
      <Section title="How this site works">
        <ul className="max-w-3xl space-y-3 text-[15px] leading-relaxed text-ink-2">
          <li>
            <span className="font-semibold text-ink">Server components query the views directly</span> over a read-only Postgres role
            that can see the views and nothing else. There is no API layer to maintain.
          </li>
          <li>
            <span className="font-semibold text-ink">Pages are statically generated and regenerated daily.</span> If the database is
            unreachable during a regeneration, the last good version keeps serving, so a paused free-tier database never takes the
            site down.
          </li>
          <li>
            <span className="font-semibold text-ink">The archive searches client-side.</span> All {fmtInt(h.features)} rows ship once
            (compact keys, image hashes rather than URLs) and every filter is instant. Filter state lives in the URL, so any view is
            shareable.
          </li>
        </ul>
      </Section>

      {/* ── Limits ───────────────────────────────────────── */}
      <Section title="What the data can't tell you">
        <ul className="grid max-w-4xl gap-x-10 gap-y-4 text-[15px] leading-relaxed text-ink-2 md:grid-cols-2">
          <li>
            <span className="font-semibold text-ink">Label location isn&apos;t artist location.</span> A London label can sign a Lagos
            artist. Every geographic claim here is about labels.
          </li>
          <li>
            <span className="font-semibold text-ink">There&apos;s no denominator.</span> Bandcamp&apos;s catalogue by country isn&apos;t
            public, so coverage share can&apos;t be read as editorial preference.
          </li>
          <li>
            <span className="font-semibold text-ink">&ldquo;Self-released&rdquo; is rule-derived</span> and also absorbs rows where the
            label failed to parse.
          </li>
          <li>
            <span className="font-semibold text-ink">{fmtPct(h.untaggedShare)} of features have no genre tag</span>, mostly early ones.
            Per-genre statistics exclude them.
          </li>
          <li>
            <span className="font-semibold text-ink">Spotify matching is heuristic.</span> A non-match can mean the album isn&apos;t on
            Spotify or that the names differ; {fmtPct(health.spotifyMatchRate)} matched.
          </li>
          <li>
            <span className="font-semibold text-ink">It describes coverage, not intent.</span> Observational data can show what was
            featured, not why.
          </li>
        </ul>
        <p className="mt-8 text-sm text-muted">
          Full analysis with statistical tests:{" "}
          <a href={repoFile("docs/findings.md")} target="_blank" rel="noreferrer" className="text-accent hover:underline">
            findings.md
          </a>{" "}
          · Column definitions:{" "}
          <a href={repoFile("docs/data_dictionary.md")} target="_blank" rel="noreferrer" className="text-accent hover:underline">
            data dictionary
          </a>{" "}
          · Source:{" "}
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="text-accent hover:underline">
            GitHub
          </a>
        </p>
      </Section>
    </>
  );
}

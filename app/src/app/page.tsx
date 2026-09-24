import Link from "next/link";
import LineChart from "@/components/charts/LineChart";
import LiftBars from "@/components/charts/LiftBars";
import WriterScatter from "@/components/charts/WriterScatter";
import Cover from "@/components/Cover";
import DataTable from "@/components/DataTable";
import { ButtonLink, Card, Caveat, ChartTitle, Container, Eyebrow, Stat } from "@/components/ui";
import { fmtInt, fmtPct } from "@/lib/format";
import { TABLEAU_URL } from "@/lib/links";
import { getCountries, getHeadline, getLatestWithCovers, getRosterShift, getScenes, getWriters, getYearly } from "@/lib/queries";

// Statically generated, then regenerated at most once a day. If the database
// is unreachable during a regeneration, the last good page keeps serving.
export const revalidate = 86400;

function Finding({
  n,
  kicker,
  title,
  children,
  chart,
}: {
  n: string;
  kicker: string;
  title: string;
  children: React.ReactNode;
  chart: React.ReactNode;
}) {
  return (
    <section className="border-t border-line py-14 sm:py-20">
      <Container className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-12">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">
            <span className="text-accent tnum">{n}</span> · {kicker}
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-ink sm:text-[28px] sm:leading-tight">{title}</h2>
          <div className="mt-4 space-y-3 text-[15px] leading-relaxed text-ink-2">{children}</div>
        </div>
        <Card className="self-start">{chart}</Card>
      </Container>
    </section>
  );
}

export default async function Home() {
  const [h, yearly, scenes, writers, latest, countries, roster] = await Promise.all([
    getHeadline(),
    getYearly(),
    getScenes(12),
    getWriters(15),
    getLatestWithCovers(12),
    getCountries(),
    getRosterShift(),
  ]);

  // Geography: peak year vs the last complete year.
  const lastYear = yearly[yearly.length - 1];
  const partial = String(lastYear.year) === h.lastDate.slice(0, 4) && h.lastDate.slice(5) < "12-15";
  const full = partial ? yearly.slice(0, -1) : yearly;
  const peak = full.reduce((a, b) => (b.usShare > a.usShare ? b : a));
  const lastFull = full[full.length - 1];
  const usPoints = yearly.map((r) => ({
    x: r.year,
    y: r.usShare,
    note: `${fmtInt(Math.round((r.usShare / 100) * r.located))} of ${fmtInt(r.located)} located features`,
  }));
  // The years between the peak and the break, to describe the plateau honestly.
  const plateau = full.filter((r) => r.year > peak.year && r.year < lastFull.year - 1);
  const avgPerYear = Math.round(full.filter((r) => r.year >= peak.year).reduce((s, r) => s + r.features, 0) / full.filter((r) => r.year >= peak.year).length);

  // Structure: self-released share by year, and the countries at either end.
  const indieMin = Math.min(...yearly.map((r) => r.indieShare));
  const indieMax = Math.max(...yearly.map((r) => r.indieShare));
  const indiePoints = yearly.map((r) => ({ x: r.year, y: r.indieShare, note: `${fmtInt(r.features)} features` }));
  // A 30-feature floor keeps one-label countries from topping the ranking.
  const byIndie = countries.filter((c) => c.features >= 30).sort((a, b) => b.indieShare - a.indieShare);
  const [hi1, hi2] = byIndie;
  const [lo2, lo1] = byIndie.slice(-2);

  // Editorial: the most specialised regular writer and the most prolific one.
  const regulars = writers.filter((w) => w.reviews >= 20).sort((a, b) => a.entropy - b.entropy);
  const specialist = regulars[0];
  const prolific = writers[0];

  // Scenes: the highest lift, and the highest lift that clears the evidence bar.
  const top = scenes[0];
  const credible = scenes.find((s) => s.features >= 5)!;
  const biggest = scenes.filter((s) => s.features >= 5).sort((a, b) => b.features - a.features)[0];

  return (
    <>
      {/* ── Hero ─────────────────────────────────────────── */}
      <Container className="grid items-center gap-10 pb-14 pt-12 sm:pt-16 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-14">
        <div>
          <Eyebrow>Bandcamp Daily · Album of the Day · {h.firstDate.slice(0, 4)}–{h.lastDate.slice(0, 4)}</Eyebrow>
          <h1 className="mt-4 text-4xl font-semibold leading-[1.08] tracking-tight text-ink sm:text-5xl">
            Where does editorial attention actually go?
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-2 sm:text-lg">
            Bandcamp Daily has picked an Album of the Day almost every weekday since 2011, and a feature there can make an
            unknown artist&apos;s year. I scraped all {fmtInt(h.features)} of them, matched them to Spotify, loaded them into a
            Postgres warehouse and asked how that attention is distributed.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <ButtonLink href="/archive" primary>
              Browse the archive
            </ButtonLink>
            <ButtonLink href="/map">Explore the map</ButtonLink>
            <ButtonLink href={TABLEAU_URL} external>
              Tableau dashboard
            </ButtonLink>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-2" aria-label="The most recent features">
          {latest.map((f, i) => (
            <Link
              key={f.id}
              href={`/archive?album=${f.id}`}
              className="group relative overflow-hidden rounded-md ring-1 ring-white/5"
              title={`${f.album} — ${f.artist}`}
            >
              <Cover img={f.img} artist={f.artist} album={f.album} eager={i < 8} className="transition-transform duration-300 group-hover:scale-105" />
            </Link>
          ))}
        </div>
      </Container>

      <Container className="pb-16">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <Stat label="Features analysed" value={fmtInt(h.features)} note={`${h.firstDate.slice(0, 4)}–${h.lastDate.slice(0, 4)}`} />
          <Stat label="Label countries" value={fmtInt(h.countries)} />
          <Stat label="Writers" value={fmtInt(h.writers)} />
          <Stat label="Record labels" value={fmtInt(h.labels)} />
          <Stat label="Self-released" value={fmtPct(h.indieShare)} note="no label credited" />
        </div>
      </Container>

      {/* ── 01 Geography ─────────────────────────────────── */}
      <Finding
        n="01"
        kicker="Geography"
        title={`The US share of coverage fell from ${peak.usShare.toFixed(0)}% to ${lastFull.usShare.toFixed(0)}%`}
        chart={
          <>
            <ChartTitle
              title="Share of features from US-based labels, by year"
              subtitle={`Share of features with a known label location.${partial ? ` *${lastYear.year} is year to date.` : ""}`}
            />
            <LineChart
              data={usPoints}
              yMax={75}
              yTicks={[0, 25, 50, 75]}
              labelAt={[peak.year, lastFull.year, lastYear.year]}
              partialLast={partial}
              reference={{ y: h.usShare, label: `All-time ${h.usShare.toFixed(1)}%` }}
              valueLabel="from US labels"
              ariaLabel={`Line chart: US share of features by year, from ${peak.usShare.toFixed(1)}% in ${peak.year} to ${lastFull.usShare.toFixed(1)}% in ${lastFull.year}.`}
            />
            <DataTable
              caption="US share of Album of the Day features by year"
              rows={yearly}
              columns={[
                { label: "Year", value: (r) => r.year },
                { label: "Located features", value: (r) => fmtInt(r.located), numeric: true },
                { label: "US share", value: (r) => fmtPct(r.usShare), numeric: true },
              ]}
            />
          </>
        }
      >
        <p>
          Across the whole archive, <strong className="font-semibold text-ink">{fmtPct(h.usShare)}</strong> of features come from
          US-based labels and the top three countries account for{" "}
          <strong className="font-semibold text-ink">{fmtPct(h.top3Share)}</strong>. The static number is the less interesting one.
        </p>
        <p>
          The US share peaked at {fmtPct(peak.usShare)} in {peak.year}, moved between{" "}
          {Math.min(...plateau.map((r) => r.usShare)).toFixed(0)}% and {Math.max(...plateau.map((r) => r.usShare)).toFixed(0)}% for the
          next {plateau.length} years, then dropped sharply to {fmtPct(lastFull.usShare)} in {lastFull.year}. Output stayed flat at about {avgPerYear} features a year, so international
          coverage grew by <em>reallocating</em> attention, not by adding more of it.
        </p>
        <p>
          It wasn&apos;t a change of writers. {roster.continuingShare.toFixed(0)}% of features since 2024 came from people already
          writing for the section in 2018–23, and those same {roster.writers} writers&apos; US share fell from{" "}
          {fmtPct(roster.before)} to {fmtPct(roster.after)}. The shift happened inside the existing roster.
        </p>
        <Caveat>
          These are label locations, not artist locations, and Bandcamp&apos;s catalogue composition isn&apos;t public, so the level
          can&apos;t be read as editorial preference. The trend over time is the robust part.
        </Caveat>
      </Finding>

      {/* ── 02 Structure ─────────────────────────────────── */}
      <Finding
        n="02"
        kicker="Structure"
        title="Two thirds of features are self-released, every single year"
        chart={
          <>
            <ChartTitle title="Share of features with no record label, by year" subtitle={partial ? `*${lastYear.year} is year to date.` : undefined} />
            <LineChart
              data={indiePoints}
              yMax={100}
              yTicks={[0, 25, 50, 75, 100]}
              labelAt={[yearly.find((r) => r.indieShare === indieMin)!.year, yearly.find((r) => r.indieShare === indieMax)!.year]}
              partialLast={partial}
              reference={{ y: h.indieShare, label: `All-time ${h.indieShare.toFixed(1)}%` }}
              valueLabel="self-released"
              ariaLabel={`Line chart: self-released share by year, ranging from ${indieMin.toFixed(1)}% to ${indieMax.toFixed(1)}%.`}
            />
            <DataTable
              caption="Self-released share of features by year"
              rows={yearly}
              columns={[
                { label: "Year", value: (r) => r.year },
                { label: "Features", value: (r) => fmtInt(r.features), numeric: true },
                { label: "Self-released", value: (r) => fmtPct(r.indieShare), numeric: true },
              ]}
            />
          </>
        }
      >
        <p>
          <strong className="font-semibold text-ink">{fmtPct(h.indieShare)}</strong> of Album of the Day features credit no label at
          all, and the ratio has stayed between {indieMin.toFixed(0)}% and {indieMax.toFixed(0)}% every year. The section&apos;s
          centre of gravity isn&apos;t small labels. It&apos;s artists with no label.
        </p>
        <p>
          The spread by country is wide. Among countries with 30+ features, {hi1.country} ({hi1.indieShare.toFixed(0)}%) and{" "}
          {hi2.country} ({hi2.indieShare.toFixed(0)}%) run well above average, while {lo1.country} ({lo1.indieShare.toFixed(0)}%) and{" "}
          {lo2.country} ({lo2.indieShare.toFixed(0)}%) run well below. That points to different independent-music infrastructures
          rather than different editorial treatment.
        </p>
        <Caveat>
          &ldquo;Self-released&rdquo; is derived by rule (artist and credited label are the same entity), so it also absorbs rows
          where the label failed to parse. Treat it as a well-founded estimate, not a census.
        </Caveat>
      </Finding>

      {/* ── 03 Editorial ─────────────────────────────────── */}
      <Finding
        n="03"
        kicker="Editorial"
        title={`15 writers produced ${fmtPct(h.top15WriterShare)} of all coverage`}
        chart={
          <>
            <ChartTitle
              title="Some writers stay in one lane; others cover everything"
              subtitle={`Writers with 15+ reviews. Genre spread is Shannon entropy: 0 bits = one genre only.`}
            />
            <WriterScatter writers={writers} labelNames={[specialist.author, regulars[1].author, prolific.author]} />
            <DataTable
              caption="Writers with 15 or more reviews"
              rows={writers}
              columns={[
                { label: "Writer", value: (r) => r.author },
                { label: "Reviews", value: (r) => r.reviews, numeric: true },
                { label: "Genres", value: (r) => r.genres, numeric: true },
                { label: "Countries", value: (r) => r.countries, numeric: true },
                { label: "Entropy (bits)", value: (r) => r.entropy.toFixed(2), numeric: true },
                { label: "Self-released", value: (r) => fmtPct(r.indieShare, 0), numeric: true },
              ]}
            />
          </>
        }
      >
        <p>
          {fmtInt(h.writers)} people have written an Album of the Day, but the 15 most active wrote{" "}
          <strong className="font-semibold text-ink">{fmtPct(h.top15WriterShare)}</strong> of them. Individual writers materially
          shape what gets surfaced.
        </p>
        <p>
          They also cover very different ground. {specialist.author} has covered just {specialist.genres} genres in{" "}
          {specialist.reviews} reviews ({specialist.entropy.toFixed(2)} bits); {prolific.author} spans {prolific.genres} genres and{" "}
          {prolific.countries} countries across {prolific.reviews}. Chi-square tests against the archive-wide genre mix show
          significant deviations for most of the top 15.
        </p>
        <Caveat>
          &ldquo;Bias&rdquo; here is statistical: systematic deviation from the site average. With no visible assignment mechanism,
          a writer&apos;s taste, an editor&apos;s assignments and what was submitted at the time can&apos;t be separated.
        </Caveat>
      </Finding>

      {/* ── 04 Scenes ────────────────────────────────────── */}
      <Finding
        n="04"
        kicker="Scenes"
        title="City scenes are real, but narrower than the clichés"
        chart={
          <>
            <ChartTitle
              title="Genres a city over-indexes on (lift)"
              subtitle="Lift = genre's share of a city's features ÷ its share of the whole archive. Top 12 pairs."
            />
            <LiftBars scenes={scenes} />
            <DataTable
              caption="City and genre lift"
              rows={scenes}
              columns={[
                { label: "City", value: (r) => (r.state ? `${r.city}, ${r.state}` : `${r.city}, ${r.country}`) },
                { label: "Genre", value: (r) => r.genre },
                { label: "Features", value: (r) => r.features, numeric: true },
                { label: "City total", value: (r) => r.cityFeatures, numeric: true },
                { label: "Lift", value: (r) => `${r.lift.toFixed(2)}×`, numeric: true },
              ]}
            />
          </>
        }
      >
        <p>
          <strong className="font-semibold text-ink">Lift</strong> compares a genre&apos;s share inside one city with its share across
          the archive; 5× means five times as common there. The metric is badly behaved in the tail, so the SQL view only keeps
          cities with 10+ tagged features and pairs with 3+.
        </p>
        <p>
          Even then, evidence matters more than the ratio. The highest lift, {top.city} {top.genre.toLowerCase()} ({top.lift.toFixed(1)}×),
          rests on just {top.features} records. {credible.city} {credible.genre.toLowerCase()} ({credible.features} of{" "}
          {credible.cityFeatures} features) and {biggest.city} {biggest.genre.toLowerCase()} ({biggest.features} of {biggest.cityFeatures})
          are the credible scenes.
        </p>
        <Caveat>
          Several of music writing&apos;s favourite associations, like Bristol and trip-hop, don&apos;t clear the floor. That&apos;s not
          because they&apos;re false; the archive just doesn&apos;t have enough features from those cities to test them.
        </Caveat>
      </Finding>

      {/* ── Explore ──────────────────────────────────────── */}
      <section className="border-t border-line pt-14 sm:pt-20">
        <Container>
          <h2 className="text-2xl font-semibold tracking-tight text-ink">Keep exploring</h2>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { href: "/archive", title: "The archive", body: `Search all ${fmtInt(h.features)} features by artist, genre, city or writer.` },
              { href: "/map", title: "The map", body: `Coverage across ${h.countries} countries. Click one to see its scenes.` },
              { href: "/methodology", title: "How it's built", body: "Pipeline, warehouse model, data quality and caveats." },
              { href: TABLEAU_URL, title: "Tableau dashboard", body: "The analysis as a three-tab BI dashboard.", external: true },
            ].map((c) => {
              const inner = (
                <>
                  <p className="font-semibold text-ink">
                    {c.title} <span className="text-accent">{c.external ? "↗" : "→"}</span>
                  </p>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{c.body}</p>
                </>
              );
              const cls = "block rounded-xl border border-line bg-surface p-5 transition-colors hover:border-baseline hover:bg-surface-2";
              return c.external ? (
                <a key={c.href} href={c.href} target="_blank" rel="noreferrer" className={cls}>
                  {inner}
                </a>
              ) : (
                <Link key={c.href} href={c.href} className={cls}>
                  {inner}
                </Link>
              );
            })}
          </div>
        </Container>
      </section>
    </>
  );
}

"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import type { CountryStat } from "@/lib/queries";
import type { Point, Shape } from "@/lib/geo";
import { ISO_NUMERIC } from "@/lib/countries";
import { fmtDate, fmtInt, fmtPct } from "@/lib/format";
import Cover from "@/components/Cover";
import { CloseIcon } from "@/components/icons";
import { Tooltip, TipRow, TipTitle } from "@/components/charts/shared";

// Six ordinal classes on one teal ramp (validated against the dark surface).
const BINS = [
  { min: 100, label: "100+", color: "var(--seq-6)" },
  { min: 30, label: "30–99", color: "var(--seq-5)" },
  { min: 10, label: "10–29", color: "var(--seq-4)" },
  { min: 5, label: "5–9", color: "var(--seq-3)" },
  { min: 2, label: "2–4", color: "var(--seq-2)" },
  { min: 1, label: "1", color: "var(--seq-1)" },
];
const binColor = (n: number) => BINS.find((b) => n >= b.min)!.color;

export default function WorldMap({
  shapes,
  points,
  stats,
  width: W,
  height: H,
}: {
  shapes: Shape[];
  points: Point[];
  stats: CountryStat[];
  width: number;
  height: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ c: CountryStat; x: number; y: number; w: number } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const byIso = useMemo(() => {
    const m = new Map<string, CountryStat>();
    for (const s of stats) {
      const iso = ISO_NUMERIC[s.country];
      if (iso) m.set(iso, s);
    }
    return m;
  }, [stats]);
  const byName = useMemo(() => new Map(stats.map((s) => [s.country, s])), [stats]);
  const sel = selected ? (byName.get(selected) ?? null) : null;
  const total = stats.reduce((a, s) => a + s.features, 0);

  const showAt = (c: CountryStat, clientX: number, clientY: number) => {
    const r = box.current!.getBoundingClientRect();
    setHover({ c, x: clientX - r.left, y: clientY - r.top, w: r.width });
  };
  const showAtMapPoint = (c: CountryStat, mx: number, my: number) => {
    const r = box.current!.getBoundingClientRect();
    const k = r.width / W;
    setHover({ c, x: mx * k, y: my * k, w: r.width });
  };
  const choose = (country: string) => {
    setSelected((s) => (s === country ? null : country));
    if (window.matchMedia("(max-width: 1023px)").matches) {
      requestAnimationFrame(() => panel.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  };

  const markProps = (c: CountryStat, cx: number, cy: number) => ({
    tabIndex: 0,
    role: "button",
    "aria-label": `${c.country}: ${fmtInt(c.features)} features`,
    "aria-pressed": selected === c.country,
    onPointerMove: (e: React.PointerEvent) => showAt(c, e.clientX, e.clientY),
    onPointerLeave: () => setHover(null),
    onFocus: () => showAtMapPoint(c, cx, cy),
    onBlur: () => setHover(null),
    onClick: () => choose(c.country),
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose(c.country);
      }
    },
    className: "cursor-pointer outline-none focus-visible:stroke-[var(--ink)] focus-visible:stroke-[1.5px]",
  });

  return (
    <div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div>
          <div ref={box} className="relative rounded-2xl border border-line bg-surface p-2 sm:p-4">
            <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="group" aria-label="World map of Album of the Day features by label country">
              {shapes.map((s) => {
                const c = byIso.get(s.id);
                if (!c) return <path key={s.id} d={s.d} fill="var(--land)" stroke="var(--surface)" strokeWidth={0.6} />;
                const isSel = selected === c.country;
                return (
                  <path
                    key={s.id}
                    d={s.d}
                    fill={binColor(c.features)}
                    stroke={isSel ? "var(--ink)" : "var(--surface)"}
                    strokeWidth={isSel ? 1.5 : 0.6}
                    opacity={hover && hover.c !== c && !isSel ? 0.75 : 1}
                    {...markProps(c, s.cx, s.cy)}
                  />
                );
              })}
              {/* Too small for a polygon at this resolution: drawn as dots. */}
              {points.map((p) => {
                const c = byName.get(p.country);
                if (!c) return null;
                return (
                  <circle
                    key={p.country}
                    cx={p.x}
                    cy={p.y}
                    r={4.5}
                    fill={binColor(c.features)}
                    stroke={selected === c.country ? "var(--ink)" : "var(--surface)"}
                    strokeWidth={2}
                    {...markProps(c, p.x, p.y)}
                  />
                );
              })}
            </svg>

            {hover && (
              <Tooltip x={hover.x} y={hover.y} containerWidth={hover.w}>
                <TipTitle>{hover.c.country}</TipTitle>
                <TipRow value={fmtInt(hover.c.features)} label={`features · ${fmtPct(hover.c.pct)} of all`} />
                <div className="mt-1 text-ink-2">
                  {fmtPct(hover.c.indieShare, 0)} self-released
                  {hover.c.topGenres[0] && <> · top genre {hover.c.topGenres[0].genre}</>}
                </div>
                <div className="mt-1 text-[11px] text-muted">Click for details</div>
              </Tooltip>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-2" aria-label="Legend">
            <span className="text-muted">Features per country</span>
            {[...BINS].reverse().map((b) => (
              <span key={b.label} className="inline-flex items-center gap-1.5">
                <span className="h-3 w-5 rounded-sm" style={{ background: b.color }} />
                {b.label}
              </span>
            ))}
            <span className="inline-flex items-center gap-1.5">
              <span className="h-3 w-5 rounded-sm border border-line" style={{ background: "var(--land)" }} />
              none
            </span>
          </div>
        </div>

        <div ref={panel} className="scroll-mt-24">
          {sel ? <CountryPanel c={sel} onClose={() => setSelected(null)} /> : <TopList stats={stats} total={total} onPick={choose} />}
        </div>
      </div>

      {/* The table twin: every country, reachable without the map. */}
      <div className="mt-14">
        <h2 className="text-lg font-semibold text-ink">All {stats.length} countries</h2>
        <p className="mt-1 text-sm text-muted">Select a country to see it on the map.</p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <caption className="sr-only">Album of the Day features by label country</caption>
            <thead className="bg-surface-2 text-xs text-muted">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Country</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Features</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Share</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Artists</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Self-released</th>
                <th scope="col" className="px-3 py-2 font-medium">Top genre</th>
                <th scope="col" className="px-3 py-2 font-medium">First featured</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((c) => (
                <tr key={c.country} className={`border-t border-line ${selected === c.country ? "bg-surface-2" : ""}`}>
                  <td className="px-3 py-1.5">
                    <button
                      onClick={() => {
                        setSelected(c.country);
                        box.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                      }}
                      className="text-ink hover:text-accent"
                    >
                      {c.country}
                    </button>
                  </td>
                  <td className="px-3 py-1.5 text-right text-ink-2 tnum">{fmtInt(c.features)}</td>
                  <td className="px-3 py-1.5 text-right text-ink-2 tnum">{fmtPct(c.pct)}</td>
                  <td className="px-3 py-1.5 text-right text-ink-2 tnum">{fmtInt(c.artists)}</td>
                  <td className="px-3 py-1.5 text-right text-ink-2 tnum">{fmtPct(c.indieShare, 0)}</td>
                  <td className="px-3 py-1.5 text-ink-2">{c.topGenres[0]?.genre ?? "—"}</td>
                  <td className="px-3 py-1.5 text-ink-2 tnum">{c.firstFeature.slice(0, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function TopList({ stats, total, onPick }: { stats: CountryStat[]; total: number; onPick: (c: string) => void }) {
  const top = stats.slice(0, 10);
  const max = top[0].features;
  return (
    <div className="rounded-2xl border border-line bg-surface p-5">
      <h2 className="text-sm font-semibold text-ink">Top 10 label countries</h2>
      <p className="mt-0.5 text-xs text-muted">
        {fmtPct((top.slice(0, 3).reduce((a, c) => a + c.features, 0) / total) * 100)} of located features come from the top three.
      </p>
      <ul className="mt-4 space-y-1">
        {top.map((c) => (
          <li key={c.country}>
            <button onClick={() => onPick(c.country)} className="group w-full rounded-md px-2 py-1.5 text-left hover:bg-surface-2">
              <div className="flex items-baseline justify-between text-sm">
                <span className="text-ink group-hover:text-accent">{c.country}</span>
                <span className="text-xs text-ink-2 tnum">{fmtInt(c.features)}</span>
              </div>
              <div className="mt-1 h-1.5 rounded-r-[3px] bg-series" style={{ width: `${Math.max(2, (c.features / max) * 100)}%` }} />
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-muted">Click any country on the map, or a name here.</p>
    </div>
  );
}

function CountryPanel({ c, onClose }: { c: CountryStat; onClose: () => void }) {
  const gMax = c.topGenres[0]?.n ?? 1;
  return (
    <div className="rounded-2xl border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">{c.country}</h2>
          <p className="mt-0.5 text-sm text-ink-2">
            <span className="font-semibold text-ink tnum">{fmtInt(c.features)}</span> features · {fmtPct(c.pct)} of all
          </p>
        </div>
        <button onClick={onClose} aria-label="Clear selection" className="-mr-2 -mt-1 rounded-full p-2 text-muted hover:bg-surface-3 hover:text-ink">
          <CloseIcon className="h-4 w-4" />
        </button>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
        {[
          ["Artists", fmtInt(c.artists)],
          ["Labels", fmtInt(c.labels)],
          ["Genres", fmtInt(c.genres)],
          ["Self-released", fmtPct(c.indieShare, 0)],
        ].map(([k, v]) => (
          <div key={k} className="rounded-lg bg-surface-2 px-3 py-2">
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="font-semibold text-ink">{v}</dd>
          </div>
        ))}
      </dl>

      {c.topGenres.length > 0 && (
        <div className="mt-5">
          <h3 className="text-xs text-muted">Top genres</h3>
          <ul className="mt-2 space-y-1.5">
            {c.topGenres.map((g) => (
              <li key={g.genre} className="grid grid-cols-[6.5rem_1fr_2rem] items-center gap-2 text-sm">
                <span className="truncate text-ink-2">{g.genre}</span>
                <span className="h-1.5 rounded-r-[3px] bg-series" style={{ width: `${Math.max(4, (g.n / gMax) * 100)}%` }} />
                <span className="text-right text-xs text-ink-2 tnum">{g.n}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {c.topCities.length > 0 && (
        <div className="mt-5">
          <h3 className="text-xs text-muted">Top cities</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-2">
            {c.topCities.map((t, i) => (
              <span key={t.city}>
                {t.city} <span className="text-muted tnum">({t.n})</span>
                {i < c.topCities.length - 1 ? " · " : ""}
              </span>
            ))}
          </p>
        </div>
      )}

      {c.covers.length > 0 && (
        <div className="mt-5">
          <h3 className="text-xs text-muted">Latest features</h3>
          <div className="mt-2 grid grid-cols-6 gap-1.5">
            {c.covers.map((v) => (
              <Link key={v.id} href={`/archive?album=${v.id}`} title={`${v.album} — ${v.artist}`} className="overflow-hidden rounded ring-1 ring-white/5">
                <Cover img={v.img} artist={v.artist} album={v.album} size={64} />
              </Link>
            ))}
          </div>
        </div>
      )}

      <p className="mt-5 text-xs text-muted">
        First featured {fmtDate(c.firstFeature)} · latest {fmtDate(c.latestFeature)}
      </p>
      <Link
        href={`/archive?country=${encodeURIComponent(c.country)}`}
        className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-sm font-medium text-bg hover:bg-white"
      >
        Browse all {fmtInt(c.features)} in the archive →
      </Link>
    </div>
  );
}

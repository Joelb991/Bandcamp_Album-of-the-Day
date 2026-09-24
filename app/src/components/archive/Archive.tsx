"use client";

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Feature } from "@/lib/queries";
import { fmtDate, fmtInt, place } from "@/lib/format";
import Cover from "@/components/Cover";
import { CloseIcon, SearchIcon } from "@/components/icons";
import Detail from "./Detail";

export type Option = { value: string; n: number };
export type Options = { genres: Option[]; countries: Option[]; years: Option[] };

type Filters = {
  q: string;
  genre: string;
  country: string;
  year: string;
  type: "" | "self" | "label";
  city: string;
  author: string;
  sort: "new" | "old";
};

const EMPTY: Filters = { q: "", genre: "", country: "", year: "", type: "", city: "", author: "", sort: "new" };
const PAGE = 48;
const KEYS = Object.keys(EMPTY) as (keyof Filters)[];

const norm = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // strip accents so "Reunion" finds "Réunion"
    .toLowerCase();

function fromParams(p: URLSearchParams): { filters: Filters; album: string | null } {
  const f = { ...EMPTY };
  for (const k of KEYS) {
    const v = p.get(k);
    if (v) (f as Record<string, string>)[k] = v;
  }
  if (f.type !== "self" && f.type !== "label") f.type = "";
  if (f.sort !== "old") f.sort = "new";
  return { filters: f, album: p.get("album") };
}

/** Reads the URL (needs a Suspense boundary on a static page). */
export function ArchiveFromUrl(props: { features: Feature[]; options: Options }) {
  const params = useSearchParams();
  const { filters, album } = fromParams(new URLSearchParams(params.toString()));
  return <Archive {...props} initial={filters} initialAlbum={album} />;
}

export default function Archive({
  features,
  options,
  initial = EMPTY,
  initialAlbum = null,
}: {
  features: Feature[];
  options: Options;
  initial?: Filters;
  initialAlbum?: string | null;
}) {
  const [f, setF] = useState<Filters>(initial);
  const [shown, setShown] = useState(PAGE);
  const [openId, setOpenId] = useState<string | null>(initialAlbum);
  const q = useDeferredValue(f.q);
  const gridTop = useRef<HTMLDivElement>(null);

  const haystack = useMemo(
    () =>
      features.map((x) =>
        norm([x.artist, x.album, x.label, x.city, x.state, x.country, x.author, x.genre].filter(Boolean).join(" · ")),
      ),
    [features],
  );

  const results = useMemo(() => {
    const terms = norm(q).split(/\s+/).filter(Boolean);
    const out = features.filter((x, i) => {
      if (f.genre && (f.genre === "Untagged" ? x.genre !== null : x.genre !== f.genre)) return false;
      if (f.country && x.country !== f.country) return false;
      if (f.year && !x.d.startsWith(f.year)) return false;
      if (f.type === "self" && !x.indie) return false;
      if (f.type === "label" && x.indie) return false;
      if (f.city && x.city !== f.city) return false;
      if (f.author && x.author !== f.author) return false;
      return terms.every((t) => haystack[i].includes(t));
    });
    return f.sort === "old" ? out.reverse() : out;
  }, [features, haystack, q, f.genre, f.country, f.year, f.type, f.city, f.author, f.sort]);

  // Keep the URL in sync so any view can be shared.
  useEffect(() => {
    const p = new URLSearchParams();
    for (const k of KEYS) if (f[k] && f[k] !== EMPTY[k]) p.set(k, f[k]);
    if (openId) p.set("album", openId);
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [f, openId]);

  const set = (patch: Partial<Filters>) => {
    setF((prev) => ({ ...prev, ...patch }));
    setShown(PAGE);
  };
  const active = KEYS.some((k) => k !== "sort" && f[k] !== EMPTY[k]);
  const byId = useMemo(() => new Map(features.map((x) => [x.id, x])), [features]);
  const open = openId ? (byId.get(openId) ?? null) : null;

  // Capped so a long option ("Democratic Republic of the Congo") can't push the row onto two lines.
  const select = "control h-10 max-w-44 rounded-lg border border-line bg-surface px-3 text-sm text-ink hover:border-baseline";

  return (
    <div>
      {/* Filters: one row above everything they scope. */}
      <div className="-mx-4 border-b border-line bg-bg/90 px-4 py-3 backdrop-blur-md sm:-mx-6 sm:px-6 md:sticky md:top-[61px] md:z-30">
        <div className="flex flex-wrap gap-2">
          <label className="relative min-w-56 flex-1">
            <span className="sr-only">Search</span>
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={f.q}
              onChange={(e) => set({ q: e.target.value })}
              placeholder="Artist, album, label, city, writer…"
              className="h-10 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-muted hover:border-baseline"
            />
          </label>
          <select aria-label="Genre" className={select} value={f.genre} onChange={(e) => set({ genre: e.target.value })}>
            <option value="">All genres</option>
            {options.genres.map((o) => (
              <option key={o.value} value={o.value}>
                {o.value} ({fmtInt(o.n)})
              </option>
            ))}
          </select>
          <select aria-label="Country" className={select} value={f.country} onChange={(e) => set({ country: e.target.value })}>
            <option value="">All countries</option>
            {options.countries.map((o) => (
              <option key={o.value} value={o.value}>
                {o.value} ({fmtInt(o.n)})
              </option>
            ))}
          </select>
          <select aria-label="Year" className={select} value={f.year} onChange={(e) => set({ year: e.target.value })}>
            <option value="">All years</option>
            {options.years.map((o) => (
              <option key={o.value} value={o.value}>
                {o.value} ({fmtInt(o.n)})
              </option>
            ))}
          </select>
          <select
            aria-label="Label type"
            className={select}
            value={f.type}
            onChange={(e) => set({ type: e.target.value as Filters["type"] })}
          >
            <option value="">Label or self-released</option>
            <option value="self">Self-released only</option>
            <option value="label">On a label only</option>
          </select>
          <select aria-label="Sort" className={select} value={f.sort} onChange={(e) => set({ sort: e.target.value as Filters["sort"] })}>
            <option value="new">Newest first</option>
            <option value="old">Oldest first</option>
          </select>
        </div>

        <div className="mt-2.5 flex flex-wrap items-center gap-2 text-sm">
          <p className="text-ink-2" aria-live="polite">
            <span className="font-semibold text-ink tnum">{fmtInt(results.length)}</span>{" "}
            {results.length === 1 ? "feature" : "features"}
          </p>
          {f.city && (
            <Chip onClear={() => set({ city: "" })}>
              City: {f.city}
            </Chip>
          )}
          {f.author && (
            <Chip onClear={() => set({ author: "" })}>
              Writer: {f.author}
            </Chip>
          )}
          {active && (
            <button onClick={() => set({ ...EMPTY, sort: f.sort })} className="text-accent hover:underline">
              Clear filters
            </button>
          )}
        </div>
      </div>

      <div ref={gridTop} className="scroll-mt-40" />

      {results.length === 0 ? (
        <div className="py-24 text-center">
          <p className="text-ink">No features match those filters.</p>
          <button onClick={() => set({ ...EMPTY })} className="mt-3 text-sm text-accent hover:underline">
            Clear filters
          </button>
        </div>
      ) : (
        <ul className="mt-6 grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {results.slice(0, shown).map((x) => (
            <li key={x.id}>
              <button onClick={() => setOpenId(x.id)} className="group block w-full text-left">
                <div className="overflow-hidden rounded-md ring-1 ring-white/5">
                  <Cover img={x.img} artist={x.artist} album={x.album} className="transition-transform duration-300 group-hover:scale-[1.04]" />
                </div>
                <p className="mt-2 line-clamp-1 text-sm font-semibold text-ink group-hover:text-accent">{x.album}</p>
                <p className="line-clamp-1 text-sm text-ink-2">{x.artist}</p>
                <p className="mt-0.5 line-clamp-1 text-xs text-muted">
                  {fmtDate(x.d, { month: "short", day: undefined })} · {x.genre ?? "Untagged"}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}

      {results.length > shown && (
        <div className="mt-10 flex flex-col items-center gap-2">
          <button
            onClick={() => setShown((s) => s + PAGE * 2)}
            className="rounded-full border border-line px-5 py-2 text-sm text-ink-2 hover:border-baseline hover:bg-surface-2 hover:text-ink"
          >
            Show more
          </button>
          <p className="text-xs text-muted tnum">
            Showing {fmtInt(shown)} of {fmtInt(results.length)}
          </p>
        </div>
      )}

      <Detail
        feature={open}
        onClose={() => setOpenId(null)}
        onFilter={(patch) => {
          set({ ...EMPTY, sort: f.sort, ...patch });
          setOpenId(null);
          gridTop.current?.scrollIntoView({ behavior: "smooth" });
        }}
        placeLabel={open ? place(open.city, open.state, open.country) : ""}
      />
    </div>
  );
}

function Chip({ children, onClear }: { children: React.ReactNode; onClear: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 py-0.5 pl-3 pr-1 text-xs text-ink-2">
      {children}
      <button onClick={onClear} aria-label="Remove filter" className="rounded-full p-1 hover:bg-surface-3 hover:text-ink">
        <CloseIcon className="h-3 w-3" />
      </button>
    </span>
  );
}

const nf = new Intl.NumberFormat("en-US");

export const fmtInt = (n: number) => nf.format(Math.round(n));

/**
 * Round half up, then format. Number#toFixed rounds some halves *down* -
 * 13.95.toFixed(1) is "13.9" because 13.95 is stored as 13.9499999... - so
 * values the SQL layer already rounded (lift 13.95, entropy 0.235) would
 * disagree with Tableau and the docs by one digit.
 */
export const fixed = (n: number, digits = 1) =>
  (Math.round(n * 10 ** digits + 1e-9) / 10 ** digits).toFixed(digits);

export const fmtPct = (n: number, digits = 1) => `${fixed(n, digits)}%`;

/** "2026-05-26" -> "May 26, 2026". Parsed as UTC so the day never shifts. */
export function fmtDate(iso: string, opts: Intl.DateTimeFormatOptions = {}) {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
    ...opts,
  });
}

export const fmtYear = (iso: string) => iso.slice(0, 4);

export function place(city: string | null, state: string | null, country: string | null) {
  if (!country) return city ?? "Unknown location";
  if (!city) return country;
  if (country === "United States" && state) return `${city}, ${state}`;
  return `${city}, ${country}`;
}

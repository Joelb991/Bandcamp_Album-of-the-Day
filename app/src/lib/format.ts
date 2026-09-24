const nf = new Intl.NumberFormat("en-US");

export const fmtInt = (n: number) => nf.format(Math.round(n));

export const fmtPct = (n: number, digits = 1) => `${n.toFixed(digits)}%`;

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

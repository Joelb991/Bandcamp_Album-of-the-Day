import { Suspense } from "react";
import type { Metadata } from "next";
import Archive, { ArchiveFromUrl, type Option, type Options } from "@/components/archive/Archive";
import { Container, PageHeader } from "@/components/ui";
import { fmtInt, fmtPct } from "@/lib/format";
import { getFeatures, getHealth } from "@/lib/queries";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "Archive",
  description: "Every Bandcamp Daily Album of the Day since 2011, searchable by artist, genre, city, country, label and writer.",
};

function counts(values: (string | null)[], sortBy: "n" | "value" = "n"): Option[] {
  const m = new Map<string, number>();
  for (const v of values) if (v) m.set(v, (m.get(v) ?? 0) + 1);
  return [...m]
    .map(([value, n]) => ({ value, n }))
    .sort((a, b) => (sortBy === "n" ? b.n - a.n || a.value.localeCompare(b.value) : b.value.localeCompare(a.value)));
}

export default async function ArchivePage() {
  const [features, health] = await Promise.all([getFeatures(), getHealth()]);
  const untagged = features.filter((f) => !f.genre).length;

  const options: Options = {
    genres: [...counts(features.map((f) => f.genre)), { value: "Untagged", n: untagged }],
    countries: counts(features.map((f) => f.country)),
    years: counts(features.map((f) => f.d.slice(0, 4)), "value"),
  };

  return (
    <>
      <PageHeader eyebrow="The archive" title={`Every Album of the Day, ${fmtInt(features.length)} of them`}>
        <p>
          Search by artist, album, label, city or writer, or filter by genre, country and year. Cover art and listening links come
          from the Spotify match, which covers {fmtPct(health.spotifyMatchRate)} of the archive.
        </p>
      </PageHeader>
      <Container>
        {/* The fallback is the unfiltered archive, so the grid is in the static HTML;
            the URL-aware version takes over as soon as the page hydrates. */}
        <Suspense fallback={<Archive features={features} options={options} />}>
          <ArchiveFromUrl features={features} options={options} />
        </Suspense>
      </Container>
    </>
  );
}

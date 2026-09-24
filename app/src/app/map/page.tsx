import type { Metadata } from "next";
import WorldMap from "@/components/map/WorldMap";
import { Container, PageHeader } from "@/components/ui";
import { fmtPct } from "@/lib/format";
import { MAP_H, MAP_W, worldShapes } from "@/lib/geo";
import { getCountries, getHealth, getHeadline } from "@/lib/queries";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "Map",
  description: "Where Bandcamp Daily's Album of the Day coverage comes from, by record label country.",
};

export default async function MapPage() {
  const [stats, h, health] = await Promise.all([getCountries(), getHeadline(), getHealth()]);
  const { shapes, points } = worldShapes();

  return (
    <>
      <PageHeader eyebrow="The map" title={`Coverage from ${h.countries} countries, dominated by three`}>
        <p>
          {fmtPct(h.usShare)} of features with a known location come from US-based labels, and {fmtPct(h.top3Share)} from the US,
          UK and Canada combined. Hover a country for the headline numbers, or click it to see its genres, cities and latest
          features. Location is known for {fmtPct(health.locationCoverageRate)} of the archive; it is the <em>label&apos;s</em>{" "}
          location, not the artist&apos;s.
        </p>
      </PageHeader>
      <Container>
        <WorldMap shapes={shapes} points={points} stats={stats} width={MAP_W} height={MAP_H} />
      </Container>
    </>
  );
}

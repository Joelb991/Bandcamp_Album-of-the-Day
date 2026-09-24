import "server-only";
import { geoEqualEarth, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";
import { POINT_PLACES } from "./countries";

export const MAP_W = 960;
export const MAP_H = 470;

export type Shape = { id: string; name: string; d: string; cx: number; cy: number };
export type Point = { country: string; x: number; y: number };

/**
 * Projects the world to SVG path strings on the server, once per build, so
 * the browser gets ready-made paths instead of TopoJSON plus a projection
 * library.
 */
export function worldShapes(): { shapes: Shape[]; points: Point[] } {
  const topo = world as unknown as Topology<{ countries: GeometryCollection<{ name: string }> }>;
  const all = feature(topo, topo.objects.countries) as FeatureCollection<Geometry, { name: string }>;
  const land = all.features.filter((f) => f.id !== "010"); // drop Antarctica

  const projection = geoEqualEarth().fitExtent(
    [
      [4, 4],
      [MAP_W - 4, MAP_H - 4],
    ],
    { type: "FeatureCollection", features: land },
  );
  const path = geoPath(projection).digits(1);

  // N. Cyprus, Somaliland and Kosovo carry no ISO id in world-atlas; key them by name.
  const shapes = land.map((f: Feature<Geometry, { name: string }>) => {
    const [cx, cy] = path.centroid(f);
    return { id: f.id != null ? String(f.id) : `name:${f.properties.name}`, name: f.properties.name, d: path(f) ?? "", cx, cy };
  });

  const points = Object.entries(POINT_PLACES).map(([country, lonLat]) => {
    const [x, y] = projection(lonLat) ?? [0, 0];
    return { country, x, y };
  });

  return { shapes, points };
}

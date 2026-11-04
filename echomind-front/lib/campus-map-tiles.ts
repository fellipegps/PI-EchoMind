import type { TileLayerOptions } from "leaflet";

const OPENSTREETMAP_ORIGIN = "https://tile.openstreetmap.org";

export const CAMPUS_MAP_TILE_URL =
  process.env.NEXT_PUBLIC_MAP_TILE_URL || `${OPENSTREETMAP_ORIGIN}/{z}/{x}/{y}.png`;

export const CAMPUS_MAP_TILE_OPTIONS: TileLayerOptions = {
  attribution: process.env.NEXT_PUBLIC_MAP_TILE_ATTRIBUTION ||
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19,
  // O OpenStreetMap exige o Referer. Envie apenas a origem do site.
  referrerPolicy: CAMPUS_MAP_TILE_URL.startsWith(`${OPENSTREETMAP_ORIGIN}/`)
    ? "strict-origin"
    : undefined,
};

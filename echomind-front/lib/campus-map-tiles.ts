import type * as Leaflet from "leaflet";

const OPENSTREETMAP_ORIGIN = "https://tile.openstreetmap.org";

export const CAMPUS_MAP_TILE_URL =
  process.env.NEXT_PUBLIC_MAP_TILE_URL || `${OPENSTREETMAP_ORIGIN}/{z}/{x}/{y}.png`;

export const CAMPUS_MAP_TILE_OPTIONS: Leaflet.TileLayerOptions = {
  attribution: process.env.NEXT_PUBLIC_MAP_TILE_ATTRIBUTION ||
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19,
  // O OpenStreetMap exige o Referer. Envie apenas a origem do site.
  referrerPolicy: CAMPUS_MAP_TILE_URL.startsWith(`${OPENSTREETMAP_ORIGIN}/`)
    ? "strict-origin"
    : undefined,
};

export const CAMPUS_SATELLITE_TILE_URL = process.env.NEXT_PUBLIC_MAP_SATELLITE_TILE_URL?.trim();
export const CAMPUS_SATELLITE_TILE_ATTRIBUTION = process.env.NEXT_PUBLIC_MAP_SATELLITE_TILE_ATTRIBUTION?.trim();

export function mountCampusTiles(L: typeof Leaflet, map: Leaflet.Map) {
  const mapTiles = L.tileLayer(CAMPUS_MAP_TILE_URL, CAMPUS_MAP_TILE_OPTIONS);
  if (CAMPUS_SATELLITE_TILE_URL && CAMPUS_SATELLITE_TILE_ATTRIBUTION) {
    const satelliteTiles = L.tileLayer(CAMPUS_SATELLITE_TILE_URL, {
      attribution: CAMPUS_SATELLITE_TILE_ATTRIBUTION,
      maxZoom: 19,
    }).addTo(map);
    L.control.layers(
      { "Satélite": satelliteTiles, "Mapa": mapTiles },
      undefined,
      { collapsed: false, position: "topright" },
    ).addTo(map);
    if (CAMPUS_SATELLITE_TILE_URL.startsWith("https://api.maptiler.com/")) {
      const logo = new L.Control({ position: "bottomleft" });
      logo.onAdd = () => {
        const link = L.DomUtil.create("a", "leaflet-control");
        link.href = "https://www.maptiler.com/";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.setAttribute("aria-label", "MapTiler");
        const image = document.createElement("img");
        image.src = "https://api.maptiler.com/resources/logo.svg";
        image.alt = "MapTiler";
        image.width = 90;
        image.style.display = "block";
        link.appendChild(image);
        return link;
      };
      logo.addTo(map);
      map.on("baselayerchange", (event: Leaflet.LayersControlEvent) => {
        if (event.name === "Satélite") logo.addTo(map);
        else logo.remove();
      });
    }
  } else {
    mapTiles.addTo(map);
  }
}

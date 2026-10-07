"use client";

import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import type { Building, PathEdge, PathNode } from "@/lib/geocampus-api";

export interface GeoPoint {
  lat: number;
  lng: number;
}

interface Props {
  center: GeoPoint;
  zoom: number;
  buildings: Building[];
  nodes: PathNode[];
  edges: PathEdge[];
  draftPoint: GeoPoint | null;
  focusPoint: GeoPoint | null;
  onPickPoint?: (point: GeoPoint) => void;
}

function label(text: string): HTMLElement {
  const element = document.createElement("span");
  element.textContent = text;
  return element;
}

const MAP_TILE_URL = process.env.NEXT_PUBLIC_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const MAP_TILE_ATTRIBUTION = process.env.NEXT_PUBLIC_MAP_TILE_ATTRIBUTION ||
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const SATELLITE_TILE_URL = process.env.NEXT_PUBLIC_MAP_SATELLITE_TILE_URL?.trim();
const SATELLITE_TILE_ATTRIBUTION = process.env.NEXT_PUBLIC_MAP_SATELLITE_TILE_ATTRIBUTION?.trim();

export function GeoCampusMap({
  center,
  zoom,
  buildings,
  nodes,
  edges,
  draftPoint,
  focusPoint,
  onPickPoint,
}: Props) {
  const elementRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Leaflet.Map | null>(null);
  const leafletRef = useRef<typeof Leaflet | null>(null);
  const overlayRef = useRef<Leaflet.LayerGroup | null>(null);
  const [ready, setReady] = useState(false);
  const onPickRef = useRef(onPickPoint);

  useEffect(() => { onPickRef.current = onPickPoint; }, [onPickPoint]);

  useEffect(() => {
    let cancelled = false;
    let map: Leaflet.Map | null = null;

    void import("leaflet").then((L) => {
      if (cancelled || !elementRef.current) return;
      map = L.map(elementRef.current, {
        center: [center.lat, center.lng],
        zoom,
        scrollWheelZoom: false,
      });
      const mapTiles = L.tileLayer(MAP_TILE_URL, {
        attribution: MAP_TILE_ATTRIBUTION,
        maxZoom: 19,
      });
      if (SATELLITE_TILE_URL && SATELLITE_TILE_ATTRIBUTION) {
        const satelliteTiles = L.tileLayer(SATELLITE_TILE_URL, {
          attribution: SATELLITE_TILE_ATTRIBUTION,
          maxZoom: 19,
        }).addTo(map);
        L.control.layers(
          { "Satélite": satelliteTiles, "Mapa": mapTiles },
          undefined,
          { collapsed: false, position: "topright" },
        ).addTo(map);
        if (SATELLITE_TILE_URL.startsWith("https://api.maptiler.com/")) {
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
            if (event.name === "Satélite" && map) logo.addTo(map);
            else logo.remove();
          });
        }
      } else {
        mapTiles.addTo(map);
      }
      const overlay = L.layerGroup().addTo(map);
      map.on("click", (event: Leaflet.LeafletMouseEvent) => {
        onPickRef.current?.({ lat: event.latlng.lat, lng: event.latlng.lng });
      });
      mapRef.current = map;
      leafletRef.current = L;
      overlayRef.current = overlay;
      setReady(true);
      requestAnimationFrame(() => map?.invalidateSize());
    });

    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
      leafletRef.current = null;
      overlayRef.current = null;
    };
    // The parent keys this map by campus. Form edits must not reset its pan or zoom.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const L = leafletRef.current;
    const map = mapRef.current;
    const overlay = overlayRef.current;
    if (!L || !map || !overlay) return;
    overlay.clearLayers();

    const byId = new Map(nodes.map((node) => [node.id, node]));
    edges.filter((edge) => edge.active).forEach((edge) => {
      const from = byId.get(edge.from_node_id);
      const to = byId.get(edge.to_node_id);
      if (!from || !to) return;
      L.polyline([[from.lat, from.lng], [to.lat, to.lng]], {
        color: edge.accessible ? "#16803d" : "#b45309",
        weight: 5,
        opacity: 0.8,
      }).addTo(overlay).bindTooltip(label(edge.accessible ? "Trecho acessível" : "Trecho com barreira de acessibilidade"));
    });

    nodes.forEach((node) => {
      L.circleMarker([node.lat, node.lng], {
        radius: 5,
        color: "#fff",
        weight: 2,
        fillColor: "#2563eb",
        fillOpacity: 1,
      }).addTo(overlay).bindTooltip(label(node.label || "Ponto do caminho"));
    });

    buildings.forEach((building) => {
      L.circleMarker([building.entrance_lat, building.entrance_lng], {
        radius: 9,
        color: "#fff",
        weight: 3,
        fillColor: building.active ? "#7c3aed" : "#64748b",
        fillOpacity: 1,
      }).addTo(overlay).bindTooltip(label(`Entrada: ${building.name}`));
    });

    if (draftPoint) {
      const marker = L.marker([draftPoint.lat, draftPoint.lng], {
        draggable: Boolean(onPickRef.current),
        icon: L.divIcon({
          className: "",
          html: '<span style="display:block;width:22px;height:22px;border:3px solid white;border-radius:50%;background:#dc2626;box-shadow:0 2px 8px #0008"></span>',
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        }),
      }).addTo(overlay);
      marker.bindTooltip(label("Ponto em edição"));
      marker.on("dragend", () => {
        const point = marker.getLatLng();
        onPickRef.current?.({ lat: point.lat, lng: point.lng });
      });
    }
  }, [buildings, nodes, edges, draftPoint, ready]);

  useEffect(() => {
    if (!mapRef.current) return;
    mapRef.current.setView([center.lat, center.lng], zoom);
  }, [center.lat, center.lng, zoom, ready]);

  useEffect(() => {
    if (!focusPoint || !mapRef.current) return;
    mapRef.current.setView([focusPoint.lat, focusPoint.lng], Math.max(mapRef.current.getZoom(), 16));
  }, [focusPoint, ready]);

  return (
    <div
      ref={elementRef}
      className="h-[28rem] w-full rounded-lg border bg-muted"
      aria-label="Mapa geográfico do campus; clique para marcar um ponto durante o cadastro"
      role="application"
    />
  );
}

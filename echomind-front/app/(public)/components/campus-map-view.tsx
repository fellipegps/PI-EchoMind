"use client";

import { useEffect, useRef, useState } from "react";

import type { Building, Campus, PathEdge, PathNode } from "@/lib/geocampus-api";
import { distanceMeters } from "./campus-routing";
import type { CampusRoute, GeoPoint, LocationFix } from "./campus-routing";

type LeafletModule = typeof import("leaflet");
type MapLayers = {
  L: LeafletModule;
  map: import("leaflet").Map;
  route: import("leaflet").LayerGroup;
  current: import("leaflet").LayerGroup;
  markers: Map<string, import("leaflet").CircleMarker>;
};

const TILE_URL = process.env.NEXT_PUBLIC_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION = process.env.NEXT_PUBLIC_MAP_TILE_ATTRIBUTION ||
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export function CampusMapView({
  campus,
  buildings,
  nodes,
  edges,
  destinationId,
  route,
  fix,
  manualOrigin,
  onSelectBuilding,
  onSelectManualOrigin,
}: {
  campus: Campus;
  buildings: Building[];
  nodes: PathNode[];
  edges: PathEdge[];
  destinationId: string | null;
  route: CampusRoute | null;
  fix: LocationFix | null;
  manualOrigin: GeoPoint | null;
  onSelectBuilding: (id: string) => void;
  onSelectManualOrigin: (point: GeoPoint) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const layers = useRef<MapLayers | null>(null);
  const onSelectBuildingRef = useRef(onSelectBuilding);
  const onSelectManualOriginRef = useRef(onSelectManualOrigin);
  const lastFittedDestination = useRef<string | null>(null);
  const [ready, setReady] = useState(0);
  const [mapError, setMapError] = useState(false);

  useEffect(() => {
    onSelectBuildingRef.current = onSelectBuilding;
    onSelectManualOriginRef.current = onSelectManualOrigin;
  }, [onSelectBuilding, onSelectManualOrigin]);

  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;
    let map: import("leaflet").Map | null = null;
    lastFittedDestination.current = null;
    void import("leaflet").then((L) => {
      if (cancelled || !container.current) return;
      map = L.map(container.current, { zoomControl: true }).setView(
        [campus.center_lat, campus.center_lng], Math.min(19, campus.zoom)
      );
      L.tileLayer(TILE_URL, {
        attribution: TILE_ATTRIBUTION,
        maxZoom: 19,
      }).addTo(map);
      const byId = new Map(nodes.map((node) => [node.id, node]));
      const markers = new Map<string, import("leaflet").CircleMarker>();
      for (const edge of edges) {
        if (!edge.active) continue;
        const from = byId.get(edge.from_node_id);
        const to = byId.get(edge.to_node_id);
        if (!from || !to) continue;
        L.polyline([[from.lat, from.lng], [to.lat, to.lng]], {
          color: edge.accessible ? "#75a78a" : "#a6a9ad",
          weight: 3,
          opacity: 0.55,
          interactive: false,
          dashArray: edge.accessible ? undefined : "4 6",
        }).addTo(map);
      }
      for (const building of buildings) {
        const marker = L.circleMarker([building.entrance_lat, building.entrance_lng], {
          radius: building.id === destinationId ? 11 : 8,
          color: "#fff",
          weight: 2,
          fillColor: building.id === destinationId ? "#0b57d0" : "#304d9d",
          fillOpacity: 1,
          bubblingMouseEvents: false,
        }).addTo(map);
        const label = document.createElement("span");
        label.textContent = building.name;
        marker.bindTooltip(label, { direction: "top" });
        marker.on("click", () => onSelectBuildingRef.current(building.id));
        markers.set(building.id, marker);
      }
      map.on("click", (event) => onSelectManualOriginRef.current({
        lat: event.latlng.lat,
        lng: event.latlng.lng,
      }));
      layers.current = {
        L,
        map,
        route: L.layerGroup().addTo(map),
        current: L.layerGroup().addTo(map),
        markers,
      };
      setMapError(false);
      setReady((value) => value + 1);
      window.setTimeout(() => {
        if (!cancelled) map?.invalidateSize();
      }, 0);
    }).catch(() => {
      if (!cancelled) setMapError(true);
    });
    return () => {
      cancelled = true;
      layers.current = null;
      map?.remove();
    };
    // The map is rebuilt when institution data changes, not on each GPS update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campus, buildings, nodes, edges]);

  useEffect(() => {
    const state = layers.current;
    if (!state) return;
    for (const [id, marker] of state.markers) {
      marker.setRadius(id === destinationId ? 11 : 8);
      marker.setStyle({ fillColor: id === destinationId ? "#0b57d0" : "#304d9d" });
    }
  }, [ready, destinationId]);

  useEffect(() => {
    const state = layers.current;
    if (!state) return;
    state.route.clearLayers();
    if (route) {
      const coordinates: [number, number][] = route.points.map((point) => [point.lat, point.lng]);
      if (coordinates.length >= 2) {
        state.L.polyline(coordinates, {
          color: "#0b57d0",
          weight: 6,
          opacity: 0.9,
        }).addTo(state.route);
      }
      const first = route.points[0];
      const start = fix ?? manualOrigin;
      if (first && start && distanceMeters(first, start) > 3) {
        state.L.polyline(
          [[start.lat, start.lng], [first.lat, first.lng]],
          { color: "#db6a15", weight: 3, dashArray: "5 8", opacity: 0.8 }
        ).addTo(state.route);
      }
      const last = route.points.at(-1);
      const destination = buildings.find((item) => item.id === destinationId);
      if (last && destination && route.entranceGapM > 3) {
        state.L.polyline(
          [[last.lat, last.lng], [destination.entrance_lat, destination.entrance_lng]],
          { color: "#db6a15", weight: 3, dashArray: "5 8", opacity: 0.8 }
        ).addTo(state.route);
      }
      if (destinationId && lastFittedDestination.current !== destinationId) {
        const bounds = state.L.latLngBounds(coordinates);
        if (destination) bounds.extend([destination.entrance_lat, destination.entrance_lng]);
        state.map.fitBounds(bounds.pad(0.25), { maxZoom: 18 });
        lastFittedDestination.current = destinationId;
      }
    }
  }, [ready, route, destinationId, buildings, fix, manualOrigin]);

  useEffect(() => {
    const state = layers.current;
    if (!state) return;
    state.current.clearLayers();
    if (fix) {
      state.L.circle([fix.lat, fix.lng], {
        radius: fix.accuracy,
        color: "#0b57d0",
        weight: 1,
        fillColor: "#5c9cff",
        fillOpacity: 0.14,
        interactive: false,
      }).addTo(state.current);
      state.L.circleMarker([fix.lat, fix.lng], {
        radius: 8,
        color: "#fff",
        weight: 3,
        fillColor: "#0b57d0",
        fillOpacity: 1,
        interactive: false,
      }).addTo(state.current);
    } else if (manualOrigin) {
      state.L.circleMarker([manualOrigin.lat, manualOrigin.lng], {
        radius: 8,
        color: "#fff",
        weight: 3,
        fillColor: "#db6a15",
        fillOpacity: 1,
        interactive: false,
      }).addTo(state.current);
    }
  }, [ready, fix, manualOrigin]);

  return (
    <>
      <div ref={container} className="geo-campus-map" aria-label={`Mapa geográfico do ${campus.name}`} />
      {mapError && <p role="status">O mapa visual não carregou. Você ainda pode consultar os destinos abaixo.</p>}
    </>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./campus-map-view.module.css";
import { CAMPUS_MAP_TILE_OPTIONS, CAMPUS_MAP_TILE_URL } from "@/lib/campus-map-tiles";
import type { Building, Campus, Landmark, PlaceType } from "@/lib/geocampus-api";

export function CampusMapView({ campus, buildings, landmarks, onOpenPlace }: {
  campus: Campus;
  buildings: Building[];
  landmarks: Landmark[];
  onOpenPlace: (type: PlaceType, publicCode: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const onOpenPlaceRef = useRef(onOpenPlace);
  const [mapError, setMapError] = useState(false);

  useEffect(() => { onOpenPlaceRef.current = onOpenPlace; }, [onOpenPlace]);

  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;
    let map: import("leaflet").Map | null = null;
    void import("leaflet").then((L) => {
      if (cancelled || !container.current) return;
      map = L.map(container.current, { zoomControl: true }).setView(
        [campus.center_lat, campus.center_lng], Math.min(19, campus.zoom)
      );
      L.tileLayer(CAMPUS_MAP_TILE_URL, CAMPUS_MAP_TILE_OPTIONS).addTo(map);
      const places = [
        ...buildings.map((item) => ({ ...item, type: "building" as const, lat: item.entrance_lat, lng: item.entrance_lng })),
        ...landmarks.map((item) => ({ ...item, type: "landmark" as const })),
      ];
      for (const place of places) {
        const open = () => onOpenPlaceRef.current(place.type, place.public_code);
        const marker = L.circleMarker([place.lat, place.lng], {
          radius: 9,
          color: "var(--card)",
          weight: 2,
          fillColor: place.type === "building" ? "var(--primary)" : "var(--foreground)",
          fillOpacity: 1,
          bubblingMouseEvents: false,
        }).addTo(map);
        const label = document.createElement("span");
        label.textContent = place.name;
        marker.bindTooltip(label, { direction: "top" });
        marker.on("click", open);
        const element = marker.getElement();
        if (element) {
          element.setAttribute("tabindex", "0");
          element.setAttribute("role", "link");
          element.setAttribute("aria-label", `Abrir ficha de ${place.name}`);
          element.addEventListener("keydown", (event) => {
            if (event instanceof KeyboardEvent && event.key === "Enter") {
              event.preventDefault();
              open();
            }
          });
        }
      }
      setMapError(false);
      window.setTimeout(() => { if (!cancelled) map?.invalidateSize(); }, 0);
    }).catch(() => { if (!cancelled) setMapError(true); });
    return () => { cancelled = true; map?.remove(); };
  }, [campus, buildings, landmarks]);

  return <>
    <div ref={container} className={`geo-campus-map ${styles.map}`} role="region" aria-label={`Mapa visual de ${campus.name}`} />
    {mapError && <p role="status" className="rounded-xl border border-border bg-card p-4 text-sm leading-5 text-muted-foreground">O mapa visual não carregou. Você pode abrir as fichas dos locais pela lista abaixo.</p>}
  </>;
}

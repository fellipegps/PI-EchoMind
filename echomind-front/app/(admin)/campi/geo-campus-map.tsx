"use client";

import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import { mountCampusTiles } from "@/lib/campus-map-tiles";
import type { Landmark } from "@/lib/geocampus-api";
import styles from "./geo-campus-map.module.css";

export interface GeoPoint {
  lat: number;
  lng: number;
}

interface Props {
  center: GeoPoint;
  zoom: number;
  landmarks: Landmark[];
  draftPoint: GeoPoint | null;
  focusPoint: GeoPoint | null;
  onPickPoint?: (point: GeoPoint) => void;
}

function label(text: string): HTMLElement {
  const element = document.createElement("span");
  element.textContent = text;
  return element;
}

export function GeoCampusMap({
  center,
  zoom,
  landmarks,
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
    let resizeObserver: ResizeObserver | null = null;
    let resizeFrame: number | null = null;
    let initialFrame: number | null = null;

    void import("leaflet").then((L) => {
      if (cancelled || !elementRef.current) return;
      map = L.map(elementRef.current, {
        center: [center.lat, center.lng],
        zoom,
        scrollWheelZoom: false,
        zoomControl: false,
      });
      L.control.zoom({ zoomInTitle: "Aproximar mapa", zoomOutTitle: "Afastar mapa" }).addTo(map);
      mountCampusTiles(L, map);
      const overlay = L.layerGroup().addTo(map);
      map.on("click", (event: Leaflet.LeafletMouseEvent) => {
        onPickRef.current?.({ lat: event.latlng.lat, lng: event.latlng.lng });
      });
      mapRef.current = map;
      leafletRef.current = L;
      overlayRef.current = overlay;
      setReady(true);
      initialFrame = requestAnimationFrame(() => { if (!cancelled) map?.invalidateSize(); });
      if (typeof ResizeObserver !== "undefined") {
        resizeObserver = new ResizeObserver(() => {
          if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
          resizeFrame = requestAnimationFrame(() => { if (!cancelled) map?.invalidateSize({ pan: false }); });
        });
        resizeObserver.observe(elementRef.current);
      }
    });

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      if (initialFrame !== null) cancelAnimationFrame(initialFrame);
      if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
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

    landmarks.forEach((landmark) => {
      L.circleMarker([landmark.lat, landmark.lng], {
        radius: 7,
        color: "var(--card)",
        weight: 2,
        fillColor: landmark.active ? "var(--primary)" : "var(--muted-foreground)",
        fillOpacity: 1,
      }).addTo(overlay).bindTooltip(label(`${landmark.name}${landmark.active ? "" : " (Inativo)"}`));
    });

    if (draftPoint) {
      const marker = L.marker([draftPoint.lat, draftPoint.lng], {
        draggable: Boolean(onPickRef.current),
        title: "Ponto em edição",
        alt: "Ponto em edição; ajuste também por latitude e longitude",
        icon: L.divIcon({
          className: "",
          html: '<span style="display:block;width:22px;height:22px;border:3px solid var(--card);border-radius:50%;background:var(--destructive);box-shadow:0 2px 8px #0008"></span>',
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
  }, [landmarks, draftPoint, ready]);

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
      className={styles.map}
      aria-label="Mapa geográfico do campus; clique para marcar um ponto durante o cadastro"
      aria-describedby="geo-map-instructions"
      role="application"
    />
  );
}

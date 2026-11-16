"use client";

import { useEffect, useRef } from "react";
import {
  CAMPUS_SATELLITE_TILE_ATTRIBUTION,
  CAMPUS_SATELLITE_TILE_URL,
} from "@/lib/campus-map-tiles";
import { mountCampusGuide } from "./campus-guide/app.js";
import { campusGuideMarkup } from "./campus-guide/markup.js";
import type { MapPlace } from "./campus-guide/places";
import "./campus-guide/style.css";

const satelliteTiles = CAMPUS_SATELLITE_TILE_URL && CAMPUS_SATELLITE_TILE_ATTRIBUTION
  ? { url: CAMPUS_SATELLITE_TILE_URL, attribution: CAMPUS_SATELLITE_TILE_ATTRIBUTION }
  : undefined;

export function CampusGuideView({ modelKey, origin, placeLinks, places, showUnlinked, focusRequest, onUnavailable, onManagePlace }: {
  modelKey: string;
  origin?: [number, number];
  placeLinks: Record<string, string>;
  places: MapPlace[];
  showUnlinked: boolean;
  focusRequest: { id: string } | null;
  onUnavailable: () => void;
  onManagePlace?: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const guide = useRef<ReturnType<typeof mountCampusGuide> | null>(null);
  const view = useRef("3d");

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    element.innerHTML = campusGuideMarkup;
    const mounted = mountCampusGuide(element, { satelliteTiles, placeLinks, places, modelKey, origin, showUnlinked,
      onUnavailable, managePlace: onManagePlace, initialView: view.current, onViewChange: (mode: string) => { view.current = mode; } });
    guide.current = mounted;
    return () => {
      guide.current = null;
      mounted.destroy();
      element.replaceChildren();
    };
  }, [modelKey, origin, placeLinks, places, showUnlinked, onUnavailable, onManagePlace]);

  useEffect(() => {
    if (focusRequest) {
      container.current?.scrollIntoView({ block: "nearest" });
      guide.current?.open(focusRequest.id);
    }
  }, [focusRequest, modelKey, places]);

  return <div ref={container} className="campus-guide" />;
}

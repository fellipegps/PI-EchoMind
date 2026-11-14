"use client";

import { useEffect, useRef } from "react";
import {
  CAMPUS_SATELLITE_TILE_ATTRIBUTION,
  CAMPUS_SATELLITE_TILE_URL,
} from "@/lib/campus-map-tiles";
import { mountCampusGuide } from "./campus-guide/app.js";
import { campusGuideMarkup } from "./campus-guide/markup.js";
import "./campus-guide/style.css";

const satelliteTiles = CAMPUS_SATELLITE_TILE_URL && CAMPUS_SATELLITE_TILE_ATTRIBUTION
  ? { url: CAMPUS_SATELLITE_TILE_URL, attribution: CAMPUS_SATELLITE_TILE_ATTRIBUTION }
  : undefined;

export function CampusGuideView({ placeLinks }: { placeLinks: Record<string, string> }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    element.innerHTML = campusGuideMarkup;
    const unmount = mountCampusGuide(element, { satelliteTiles, placeLinks });
    return () => {
      unmount();
      element.replaceChildren();
    };
  }, [placeLinks]);

  return <div ref={container} className="campus-guide" />;
}

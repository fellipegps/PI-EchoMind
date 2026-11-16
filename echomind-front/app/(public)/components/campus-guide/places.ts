import { type Building, type Campus, type Landmark, type PlacePhoto } from "@/lib/geocampus-api";
import anapolisData from "@/public/campus-guide/destinations.json";

export function normalizePlaceText(name: string) {
  return name.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();
}

const anapolisCenter = { lat: -16.294, lng: -48.944 };

export function hasAnapolisModel(publicSlug: string, companyName: string, campus: Campus | undefined) {
  if (!/^unievangelica(?:-|$)/i.test(publicSlug) && !/\bunievangelica\b/.test(normalizePlaceText(companyName))) return false;
  return !campus || (
    Math.abs(campus.center_lat - anapolisCenter.lat) < 0.01 &&
    Math.abs(campus.center_lng - anapolisCenter.lng) < 0.01
  );
}

// Names from the maquete, including destinations whose public name can omit the block code.
const aliases: Record<string, readonly string[]> = {
  "bloco-a": ["bloco a"],
  biblioteca: ["bloco b1", "biblioteca central", "bloco b1 · biblioteca central"],
  "bloco-b2": ["bloco b2"],
  "bloco-c": ["bloco c"],
  "bloco-d": ["bloco d"],
  "bloco-e": ["bloco e"],
  "bloco-f": ["bloco f"],
  "bloco-g": ["bloco j"],
  "bloco-h": ["bloco h"],
  "bloco-i": ["bloco i"],
  ginasio: ["ginasio poliesportivo", "ginasio"],
  tecnologico: ["centro tecnologico"],
};

export const anapolisDestinations = anapolisData.destinations;
export type AnapolisDestination = (typeof anapolisDestinations)[number];

export type MapPlace = {
  id: string;
  destinationId?: string | null;
  name: string;
  description: string | null;
  kind: string;
  coordinates: [number, number];
  photos: PlacePhoto[];
  href: string;
  spaces?: { name: string; floor: string | null; description: string | null; href: string }[];
};

export function campusModelKey(campus: Campus | undefined, publicSlug: string, companyName: string) {
  if (!campus) return null;
  if (campus?.model_key) return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(campus.model_key) ? campus.model_key : null;
  return hasAnapolisModel(publicSlug, companyName, campus) ? "anapolis" : null;
}

export function anapolisDestinationHref(publicSlug: string, id: string) {
  return `/p/${encodeURIComponent(publicSlug)}/locais/mapa/${encodeURIComponent(id)}`;
}

export function anapolisPublishedPlaces(buildings: Building[], landmarks: Landmark[]) {
  const places = [
    ...buildings.map((place) => ({ ...place, type: "building" as const })),
    ...landmarks.map((place) => ({ ...place, type: "landmark" as const })),
  ];
  const matchesByDestination = new Map<string, (typeof places)[number]>();
  for (const place of places) {
    if (place.type === "building" && place.model_destination_id) matchesByDestination.set(place.model_destination_id, place);
  }
  for (const [id, names] of Object.entries(aliases)) {
    if (matchesByDestination.has(id)) continue;
    const matches = places.filter((place) =>
      (place.type !== "building" || !place.model_destination_id) && names.includes(normalizePlaceText(place.name)));
    if (matches.length === 1) {
      matchesByDestination.set(id, matches[0]);
    }
  }
  return matchesByDestination;
}

export function anapolisDestinationSources(destination: AnapolisDestination) {
  const sources = anapolisData.sources as Record<string, { label: string; url: string }>;
  return [...new Set([...destination.sources, ...destination.entry.sources])].map((id) => sources[id]);
}

import { fetchFromApi, fetchWithSession } from "./authenticated-fetch";

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const baseUrl = configuredApiUrl
  ? configuredApiUrl.replace(/\/$/, "")
  : process.env.NODE_ENV === "production"
    ? null
    : "http://localhost:8000";

export interface Campus {
  id: string;
  name: string;
  description: string | null;
  model_key?: string | null;
  model_defaults_applied?: boolean;
  center_lat: number;
  center_lng: number;
  zoom: number;
  active: boolean;
}

export type PlaceType = "building" | "space" | "landmark";

export interface PlacePhoto {
  id: string;
  caption: string | null;
  sort_order: number;
  url: string;
}

export interface Building {
  id: string;
  campus_id: string;
  public_code: string;
  name: string;
  description: string | null;
  category: string;
  model_destination_id?: string | null;
  entrance_lat: number;
  entrance_lng: number;
  active: boolean;
  photos: PlacePhoto[];
}

export interface IndoorSpace {
  id: string;
  campus_id: string;
  public_code: string;
  building_id: string;
  name: string;
  kind: string;
  floor: string | null;
  description: string | null;
  active: boolean;
  photos: PlacePhoto[];
}

export type IndoorSpaceDetails = Pick<IndoorSpace, "name" | "description" | "kind" | "floor" | "active">;

export interface Landmark {
  id: string;
  campus_id: string;
  public_code: string;
  name: string;
  description: string | null;
  lat: number;
  lng: number;
  active: boolean;
  photos: PlacePhoto[];
}

export type LandmarkInput = Omit<Landmark, "id" | "campus_id" | "public_code" | "photos">;

export type CampusPlace = Building | IndoorSpace | Landmark;

export interface PublicPlace {
  type: PlaceType;
  campus: Campus;
  place: CampusPlace;
  building: Building | null;
  spaces?: IndoorSpace[];
}

export interface PublicGeoCampus {
  campuses: Campus[];
  buildings: Building[];
  spaces: IndoorSpace[];
  landmarks: Landmark[];
}

export function publicPlaceHref(slug: string, type: PlaceType, publicCode: string) {
  return `/p/${encodeURIComponent(slug)}/locais/${type}/${encodeURIComponent(publicCode)}`;
}

export function campusPhotoUrl(url: string) {
  return baseUrl ? `${baseUrl}${url}` : "";
}

function resourcePath(campusId: string, resource: string, itemId?: string) {
  const base = `/campuses/${encodeURIComponent(campusId)}/${resource}`;
  return itemId ? `${base}/${encodeURIComponent(itemId)}` : base;
}

async function geoRequest<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
  responseType: "json" | "blob" = "json",
): Promise<T> {
  if (!baseUrl) throw new Error("O servidor do EchoMind ainda não está disponível.");
  const headers = new Headers(init.headers);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  const send = authenticated ? fetchWithSession : fetchFromApi;
  const response = await send(`${baseUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    if (response.status >= 500) throw new Error("O servidor não conseguiu concluir a solicitação.");
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new Error(detail || "Não foi possível concluir a solicitação.");
  }
  if (response.status === 204) return undefined as T;
  if (responseType === "blob") return response.blob() as Promise<T>;
  return response.json() as Promise<T>;
}

function photoPath(campusId: string, type: PlaceType, placeId: string, photoId?: string) {
  const path = resourcePath(campusId, `places/${type}/${encodeURIComponent(placeId)}/photos`);
  return photoId ? `${path}/${encodeURIComponent(photoId)}` : path;
}

function jsonBody(value: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(value) };
}

function resourceApi<T, I>(resource: string) {
  return {
    list: (campusId: string) => geoRequest<T[]>(resourcePath(campusId, resource)),
    create: (campusId: string, input: I) => geoRequest<T>(resourcePath(campusId, resource), jsonBody(input)),
    update: (campusId: string, id: string, input: I) =>
      geoRequest<T>(resourcePath(campusId, resource, id), { method: "PUT", body: JSON.stringify(input) }),
    delete: (campusId: string, id: string) =>
      geoRequest<void>(resourcePath(campusId, resource, id), { method: "DELETE" }),
  };
}

export const geoCampusApi = {
  campuses: {
    list: () => geoRequest<Campus[]>("/campuses"),
    prepareModel: (campusId: string) => geoRequest<void>(resourcePath(campusId, "model-defaults"), { method: "POST" }),
  },
  buildings: {
    list: (campusId: string) => geoRequest<Building[]>(resourcePath(campusId, "buildings")),
    rename: (campusId: string, id: string, name: string) => geoRequest<Building>(resourcePath(campusId, "buildings", id), {
      method: "PUT", body: JSON.stringify({ name }),
    }),
  },
  spaces: {
    list: (campusId: string) => geoRequest<IndoorSpace[]>(resourcePath(campusId, "spaces")),
    create: (campusId: string, buildingId: string, details: IndoorSpaceDetails) =>
      geoRequest<IndoorSpace>(resourcePath(campusId, "spaces"), jsonBody({ ...details, building_id: buildingId })),
    update: (campusId: string, id: string, details: IndoorSpaceDetails) => geoRequest<IndoorSpace>(resourcePath(campusId, "spaces", id), {
      method: "PUT", body: JSON.stringify(details),
    }),
  },
  landmarks: resourceApi<Landmark, LandmarkInput>("landmarks"),
  photos: {
    upload: (campusId: string, type: PlaceType, placeId: string, file: File, caption?: string) => {
      const body = new FormData();
      body.append("file", file);
      if (caption?.trim()) body.append("caption", caption.trim());
      return geoRequest<PlacePhoto>(photoPath(campusId, type, placeId), { method: "POST", body });
    },
    content: (campusId: string, type: PlaceType, placeId: string, photoId: string) =>
      geoRequest<Blob>(photoPath(campusId, type, placeId, photoId), {}, true, "blob"),
    delete: (campusId: string, type: PlaceType, placeId: string, photoId: string) =>
      geoRequest<void>(photoPath(campusId, type, placeId, photoId), { method: "DELETE" }),
  },
  publicMap: (slug: string) =>
    geoRequest<PublicGeoCampus>(`/public/${encodeURIComponent(slug)}/geo-campus`, {}, false),
  publicPlace: (slug: string, type: PlaceType, publicCode: string) =>
    geoRequest<PublicPlace>(
      `/public/${encodeURIComponent(slug)}/places/${type}/${encodeURIComponent(publicCode)}`,
      {},
      false,
    ),
};

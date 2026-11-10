import { tokenStore } from "./api";

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
  center_lat: number;
  center_lng: number;
  zoom: number;
  active: boolean;
}

export type CampusInput = Omit<Campus, "id">;

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
  entrance_lat: number;
  entrance_lng: number;
  active: boolean;
  photos: PlacePhoto[];
}

export type BuildingInput = Omit<Building, "id" | "campus_id" | "public_code" | "photos">;

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

export type IndoorSpaceInput = Omit<IndoorSpace, "id" | "campus_id" | "public_code" | "photos">;

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
  if (authenticated) {
    const token = tokenStore.get();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  } catch {
    throw new Error("Não foi possível conectar ao servidor.");
  }

  if (response.status === 401 && authenticated) {
    tokenStore.clear();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Sessão expirada. Faça login novamente.");
  }
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
    create: (input: CampusInput) => geoRequest<Campus>("/campuses", jsonBody(input)),
    update: (id: string, input: CampusInput) =>
      geoRequest<Campus>(`/campuses/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(input) }),
    delete: (id: string) => geoRequest<void>(`/campuses/${encodeURIComponent(id)}`, { method: "DELETE" }),
  },
  buildings: resourceApi<Building, BuildingInput>("buildings"),
  spaces: resourceApi<IndoorSpace, IndoorSpaceInput>("spaces"),
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

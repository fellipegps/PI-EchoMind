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

export interface Building {
  id: string;
  campus_id: string;
  name: string;
  description: string | null;
  category: string;
  entrance_lat: number;
  entrance_lng: number;
  entrance_node_id: string | null;
  active: boolean;
}

export type BuildingInput = Omit<Building, "id" | "campus_id">;

export interface IndoorSpace {
  id: string;
  campus_id: string;
  building_id: string;
  name: string;
  kind: string;
  floor: string | null;
  description: string | null;
  active: boolean;
}

export type IndoorSpaceInput = Omit<IndoorSpace, "id" | "campus_id">;

export interface PathNode {
  id: string;
  campus_id: string;
  lat: number;
  lng: number;
  label: string | null;
}

export type PathNodeInput = Omit<PathNode, "id" | "campus_id">;

export interface PathEdge {
  id: string;
  campus_id: string;
  from_node_id: string;
  to_node_id: string;
  distance_m: number | null;
  accessible: boolean;
  active: boolean;
}

export type PathEdgeInput = Omit<PathEdge, "id" | "campus_id">;

export interface PublicGeoCampus {
  campuses: Campus[];
  buildings: Building[];
  spaces: IndoorSpace[];
  nodes: PathNode[];
  edges: PathEdge[];
}

function resourcePath(campusId: string, resource: string, itemId?: string) {
  const base = `/campuses/${encodeURIComponent(campusId)}/${resource}`;
  return itemId ? `${base}/${encodeURIComponent(itemId)}` : base;
}

async function geoRequest<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  if (!baseUrl) throw new Error("O servidor do EchoMind ainda não está disponível.");
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
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
  return response.json() as Promise<T>;
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
  nodes: resourceApi<PathNode, PathNodeInput>("path-nodes"),
  edges: resourceApi<PathEdge, PathEdgeInput>("path-edges"),
  publicMap: (slug: string) =>
    geoRequest<PublicGeoCampus>(`/public/${encodeURIComponent(slug)}/geo-campus`, {}, false),
};

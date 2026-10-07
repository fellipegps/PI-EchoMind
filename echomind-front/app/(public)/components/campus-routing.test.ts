import { describe, expect, it } from "vitest";

import type { Building, PathEdge, PathNode } from "@/lib/geocampus-api";
import { distanceMeters, findCampusRoute, hasArrived, shouldAcceptFix } from "./campus-routing";

const nodes: PathNode[] = [
  { id: "a", campus_id: "campus-1", lat: 0, lng: 0, label: "Portaria" },
  { id: "b", campus_id: "campus-1", lat: 0, lng: 0.0001, label: "Praça" },
  { id: "c", campus_id: "campus-1", lat: 0.0001, lng: 0, label: "Rampa" },
  { id: "d", campus_id: "campus-1", lat: 0.0001, lng: 0.0001, label: "Entrada" },
  { id: "other", campus_id: "campus-2", lat: 0, lng: 0.0001, label: "Outro campus" },
];

const edges: PathEdge[] = [
  { id: "ab", campus_id: "campus-1", from_node_id: "a", to_node_id: "b", distance_m: 10, accessible: false, active: true },
  { id: "bd", campus_id: "campus-1", from_node_id: "b", to_node_id: "d", distance_m: 10, accessible: true, active: true },
  { id: "ac", campus_id: "campus-1", from_node_id: "a", to_node_id: "c", distance_m: 16, accessible: true, active: true },
  { id: "cd", campus_id: "campus-1", from_node_id: "c", to_node_id: "d", distance_m: 16, accessible: true, active: true },
  { id: "invalid", campus_id: "campus-2", from_node_id: "a", to_node_id: "other", distance_m: 1, accessible: true, active: true },
];

const destination: Building = {
  id: "building-1",
  campus_id: "campus-1",
  name: "Bloco A",
  description: null,
  category: "ensino",
  entrance_lat: 0.0001,
  entrance_lng: 0.0001,
  entrance_node_id: "d",
  active: true,
};

describe("campus routing", () => {
  it("usa os caminhos cadastrados mais curtos e respeita a opção acessível", () => {
    const options = {
      campusId: "campus-1", nodes, edges,
      origin: { lat: 0, lng: 0 }, destination,
    };
    const shortest = findCampusRoute({ ...options, accessibleOnly: false });
    const accessible = findCampusRoute({ ...options, accessibleOnly: true });

    expect(shortest?.nodes.map((node) => node.id)).toEqual(["a", "b", "d"]);
    expect(shortest?.distanceM).toBe(20);
    expect(accessible?.nodes.map((node) => node.id)).toEqual(["a", "c", "d"]);
    expect(accessible?.distanceM).toBe(32);
  });

  it("não inventa uma linha reta quando o grafo está desconectado ou o ponto está longe", () => {
    expect(findCampusRoute({
      campusId: "campus-1", nodes, edges: [],
      origin: { lat: 0, lng: 0 }, destination, accessibleOnly: false,
    })).toBeNull();
    expect(findCampusRoute({
      campusId: "campus-1", nodes, edges,
      origin: { lat: 1, lng: 1 }, destination, accessibleOnly: false,
    })).toBeNull();
    expect(findCampusRoute({
      campusId: "campus-2", nodes, edges,
      origin: { lat: 0, lng: 0 }, destination, accessibleOnly: false,
    })).toBeNull();
    expect(findCampusRoute({
      campusId: "campus-1",
      nodes: [...nodes, { id: "isolated", campus_id: "campus-1", lat: 0, lng: 0, label: null }],
      edges,
      origin: { lat: 0, lng: 0 }, originNodeId: "isolated",
      destination, accessibleOnly: false,
    })).toBeNull();
  });

  it("exige uma entrada vinculada a um ponto próximo do caminho", () => {
    const options = {
      campusId: "campus-1", nodes, edges,
      origin: { lat: 0, lng: 0 }, accessibleOnly: false,
    };
    expect(findCampusRoute({
      ...options,
      destination: { ...destination, entrance_node_id: null },
    })).toBeNull();
    expect(findCampusRoute({
      ...options,
      destination: { ...destination, entrance_lat: 0.001, entrance_lng: 0.001 },
    })).toBeNull();
  });

  it("ignora saltos de GPS, precisão baixa e só confirma chegada com sinal adequado", () => {
    const previous = { lat: 0, lng: 0, accuracy: 12, timestamp: 1 };
    expect(distanceMeters(previous, { lat: 0, lng: 0.0001 })).toBeGreaterThan(10);
    expect(shouldAcceptFix(previous, { lat: 0, lng: 0.00001, accuracy: 12, timestamp: 2 })).toBe(false);
    expect(shouldAcceptFix(previous, { lat: 0, lng: 0.0001, accuracy: 12, timestamp: 2 })).toBe(true);
    expect(shouldAcceptFix(previous, { lat: 0, lng: 0.0001, accuracy: 90, timestamp: 2 })).toBe(false);
    expect(hasArrived({ lat: destination.entrance_lat, lng: destination.entrance_lng, accuracy: 80, timestamp: 2 }, destination)).toBe(false);
    expect(hasArrived({ lat: destination.entrance_lat, lng: destination.entrance_lng, accuracy: 10, timestamp: 2 }, destination)).toBe(true);
  });

  it("entra no meio de um trecho longo sem obrigar retorno ao nó inicial", () => {
    const longNodes: PathNode[] = [
      { id: "start", campus_id: "campus-1", lat: 0, lng: 0, label: null },
      { id: "end", campus_id: "campus-1", lat: 0, lng: 0.002, label: null },
    ];
    const endBuilding = {
      ...destination,
      entrance_lat: 0,
      entrance_lng: 0.002,
      entrance_node_id: "end",
    };
    const route = findCampusRoute({
      campusId: "campus-1",
      nodes: longNodes,
      edges: [{ id: "long", campus_id: "campus-1", from_node_id: "start", to_node_id: "end", distance_m: 200, accessible: true, active: true }],
      origin: { lat: 0, lng: 0.0015 },
      destination: endBuilding,
      accessibleOnly: false,
    });

    expect(route?.nodes.map((node) => node.id)).toEqual(["__route_origin__", "end"]);
    expect(route?.distanceM).toBe(50);
  });
});

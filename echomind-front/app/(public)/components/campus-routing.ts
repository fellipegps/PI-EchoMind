import type { Building, PathEdge, PathNode } from "@/lib/geocampus-api";

export type GeoPoint = { lat: number; lng: number };

export type CampusRoute = {
  nodes: PathNode[];
  points: GeoPoint[];
  segmentDistancesM: number[];
  distanceM: number;
  startGapM: number;
  entranceGapM: number;
};

const EARTH_RADIUS_M = 6_371_000;
export const MAX_PATH_SNAP_M = 80;
const MAX_UNANCHORED_APPROACH_M = 25;
export const MAX_ENTRANCE_APPROACH_M = 25;

export function distanceMeters(a: GeoPoint, b: GeoPoint): number {
  const radians = (degrees: number) => (degrees * Math.PI) / 180;
  const deltaLat = radians(b.lat - a.lat);
  const deltaLng = radians(b.lng - a.lng);
  const latitudeA = radians(a.lat);
  const latitudeB = radians(b.lat);
  const haversine =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(latitudeA) * Math.cos(latitudeB) * Math.sin(deltaLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(haversine)));
}

function nearestNode(nodes: PathNode[], point: GeoPoint, maxDistanceM = MAX_PATH_SNAP_M) {
  let nearest: PathNode | null = null;
  let distance = Number.POSITIVE_INFINITY;
  for (const node of nodes) {
    const candidate = distanceMeters(point, node);
    if (candidate < distance) {
      nearest = node;
      distance = candidate;
    }
  }
  return nearest && distance <= maxDistanceM ? { node: nearest, distance } : null;
}

function projectOnEdge(point: GeoPoint, from: PathNode, to: PathNode) {
  const metersPerDegree = 111_195;
  const longitudeScale = metersPerDegree * Math.cos((point.lat * Math.PI) / 180);
  const ax = (from.lng - point.lng) * longitudeScale;
  const ay = (from.lat - point.lat) * metersPerDegree;
  const bx = (to.lng - point.lng) * longitudeScale;
  const by = (to.lat - point.lat) * metersPerDegree;
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  const fraction = lengthSquared > 0
    ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / lengthSquared))
    : 0;
  const projected = {
    lat: from.lat + (to.lat - from.lat) * fraction,
    lng: from.lng + (to.lng - from.lng) * fraction,
  };
  return { point: projected, fraction, gapM: distanceMeters(point, projected) };
}

export function findCampusRoute({
  campusId,
  nodes,
  edges,
  origin,
  originNodeId,
  destination,
  accessibleOnly,
}: {
  campusId: string;
  nodes: PathNode[];
  edges: PathEdge[];
  origin: GeoPoint;
  originNodeId?: string | null;
  destination: Building;
  accessibleOnly: boolean;
}): CampusRoute | null {
  if (destination.campus_id !== campusId) return null;
  const campusNodes = nodes.filter((node) => node.campus_id === campusId);
  const nodeById = new Map(campusNodes.map((node) => [node.id, node]));
  const entrance = { lat: destination.entrance_lat, lng: destination.entrance_lng };
  const anchoredEnd = destination.entrance_node_id
    ? nodeById.get(destination.entrance_node_id)
    : null;
  if (!anchoredEnd) return null;
  const end = { node: anchoredEnd, distance: distanceMeters(entrance, anchoredEnd) };
  if (end.distance > MAX_ENTRANCE_APPROACH_M) return null;

  const adjacency = new Map<string, { id: string; weight: number }[]>();
  let nearestEdge: {
    from: PathNode;
    to: PathNode;
    weight: number;
    point: GeoPoint;
    fraction: number;
    gapM: number;
  } | null = null;
  for (const edge of edges) {
    if (edge.campus_id !== campusId || !edge.active || (accessibleOnly && !edge.accessible)) continue;
    const from = nodeById.get(edge.from_node_id);
    const to = nodeById.get(edge.to_node_id);
    if (!from || !to || from.id === to.id) continue;
    const weight = edge.distance_m && edge.distance_m > 0
      ? edge.distance_m
      : distanceMeters(from, to);
    adjacency.set(from.id, [...(adjacency.get(from.id) ?? []), { id: to.id, weight }]);
    adjacency.set(to.id, [...(adjacency.get(to.id) ?? []), { id: from.id, weight }]);
    if (!originNodeId) {
      const projected = projectOnEdge(origin, from, to);
      if (!nearestEdge || projected.gapM < nearestEdge.gapM) {
        nearestEdge = { from, to, weight, ...projected };
      }
    }
  }

  const anchoredStart = originNodeId ? nodeById.get(originNodeId) : null;
  const nearbyNode = !originNodeId
    ? nearestNode(campusNodes, origin, MAX_UNANCHORED_APPROACH_M)
    : null;
  let start = anchoredStart
    ? { node: anchoredStart, distance: distanceMeters(origin, anchoredStart) }
    : nearbyNode;
  if (
    !originNodeId && nearestEdge && nearestEdge.gapM <= MAX_UNANCHORED_APPROACH_M &&
    (!nearbyNode || nearestEdge.gapM < nearbyNode.distance)
  ) {
    const projection = nearestEdge;
    const virtualNode: PathNode = {
      id: "__route_origin__",
      campus_id: campusId,
      lat: projection.point.lat,
      lng: projection.point.lng,
      label: "Início no caminho",
    };
    nodeById.set(virtualNode.id, virtualNode);
    adjacency.set(virtualNode.id, [
      { id: projection.from.id, weight: projection.weight * projection.fraction },
      { id: projection.to.id, weight: projection.weight * (1 - projection.fraction) },
    ]);
    start = { node: virtualNode, distance: projection.gapM };
  }
  if (!start || start.distance > MAX_PATH_SNAP_M) return null;

  // Campi costumam ter poucos cruzamentos; Dijkstra mantém o resultado estável e
  // usa a distância cadastrada pela instituição quando ela está disponível.
  const costs = new Map<string, number>([[start.node.id, 0]]);
  const previous = new Map<string, string>();
  const previousDistance = new Map<string, number>();
  const visited = new Set<string>();
  while (true) {
    let currentId: string | null = null;
    let currentCost = Number.POSITIVE_INFINITY;
    for (const [id, cost] of costs) {
      if (!visited.has(id) && cost < currentCost) {
        currentId = id;
        currentCost = cost;
      }
    }
    if (!currentId || currentId === end.node.id) break;
    visited.add(currentId);
    for (const neighbor of adjacency.get(currentId) ?? []) {
      const candidate = currentCost + neighbor.weight;
      if (candidate < (costs.get(neighbor.id) ?? Number.POSITIVE_INFINITY)) {
        costs.set(neighbor.id, candidate);
        previous.set(neighbor.id, currentId);
        previousDistance.set(neighbor.id, neighbor.weight);
      }
    }
  }
  const pathCost = costs.get(end.node.id);
  if (pathCost === undefined) return null;
  const nodeIds = [end.node.id];
  while (nodeIds[0] !== start.node.id) {
    const predecessor = previous.get(nodeIds[0]);
    if (!predecessor) return null;
    nodeIds.unshift(predecessor);
  }
  const routeNodes = nodeIds.map((id) => nodeById.get(id)!);
  return {
    nodes: routeNodes,
    points: routeNodes.map((node) => ({ lat: node.lat, lng: node.lng })),
    segmentDistancesM: nodeIds.slice(1).map((id) => previousDistance.get(id) ?? 0),
    distanceM: Math.round(start.distance + pathCost + end.distance),
    startGapM: start.distance,
    entranceGapM: end.distance,
  };
}

export type LocationFix = GeoPoint & { accuracy: number; timestamp: number };

export function shouldAcceptFix(previous: LocationFix | null, next: LocationFix): boolean {
  if (
    !Number.isFinite(next.lat) || !Number.isFinite(next.lng) ||
    !Number.isFinite(next.accuracy) || next.accuracy < 0 || next.accuracy > 60 ||
    Math.abs(next.lat) > 90 || Math.abs(next.lng) > 180 ||
    (previous && next.timestamp < previous.timestamp)
  ) return false;
  if (!previous) return true;
  const moved = distanceMeters(previous, next);
  const threshold = Math.max(6, Math.min(20, next.accuracy / 2));
  return moved >= threshold || next.accuracy <= previous.accuracy / 2;
}

export function hasArrived(fix: LocationFix | null, destination: Building): boolean {
  return Boolean(
    fix && fix.accuracy <= 25 &&
    distanceMeters(fix, { lat: destination.entrance_lat, lng: destination.entrance_lng }) <= 20
  );
}

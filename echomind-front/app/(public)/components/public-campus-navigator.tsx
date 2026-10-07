"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Accessibility, Building2, LocateFixed, MapPin, Navigation, Search } from "lucide-react";

import { geoCampusApi } from "@/lib/geocampus-api";
import type { Building, PublicGeoCampus } from "@/lib/geocampus-api";
import { CampusMapView } from "./campus-map-view";
import {
  distanceMeters,
  findCampusRoute,
  hasArrived,
  MAX_ENTRANCE_APPROACH_M,
  MAX_PATH_SNAP_M,
  shouldAcceptFix,
} from "./campus-routing";
import type { GeoPoint, LocationFix } from "./campus-routing";

import styles from "./public-campus-navigator.module.css";

type Destination = { kind: "building" | "space"; id: string } | null;

function errorForLocation(code: number): string {
  if (code === 1) return "A localização foi negada. Escolha uma origem cadastrada ou marque um ponto no mapa.";
  if (code === 2) return "Não foi possível determinar sua posição. Escolha uma origem no mapa.";
  return "A localização demorou a responder. Tente novamente ou escolha uma origem no mapa.";
}

export function PublicCampusNavigator({
  publicSlug,
  onAvailabilityChange,
}: {
  publicSlug: string;
  onAvailabilityChange?: (available: boolean) => void;
}) {
  const [data, setData] = useState<PublicGeoCampus | null>(null);
  const [campusId, setCampusId] = useState("");
  const [search, setSearch] = useState("");
  const [destination, setDestination] = useState<Destination>(null);
  const [accessibleOnly, setAccessibleOnly] = useState(false);
  const [originMode, setOriginMode] = useState<"manual" | "live">("manual");
  const [manualBuildingId, setManualBuildingId] = useState("");
  const [manualOrigin, setManualOrigin] = useState<GeoPoint | null>(null);
  const [tracking, setTracking] = useState(false);
  const [fix, setFix] = useState<LocationFix | null>(null);
  const [routeOrigin, setRouteOrigin] = useState<GeoPoint | null>(null);
  const [locationMessage, setLocationMessage] = useState("");
  const fixRef = useRef<LocationFix | null>(null);
  const routeOriginRef = useRef<GeoPoint | null>(null);
  const destinationRef = useRef<Building | null>(null);

  useEffect(() => {
    if (!publicSlug) return;
    let cancelled = false;
    void geoCampusApi.publicMap(publicSlug).then((result) => {
      if (cancelled) return;
      const activeCampuses = new Set(result.campuses.filter((campus) => campus.active).map((campus) => campus.id));
      const available = result.buildings.some((building) => building.active && activeCampuses.has(building.campus_id));
      setData(available ? result : null);
      onAvailabilityChange?.(available);
    }).catch(() => {
      if (cancelled) return;
      setData(null);
      onAvailabilityChange?.(false);
    });
    return () => { cancelled = true; };
  }, [publicSlug, onAvailabilityChange]);

  useEffect(() => {
    if (!tracking) return;
    let active = true;
    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        if (!active) return;
        const next: LocationFix = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp,
        };
        if (!Number.isFinite(next.accuracy) || next.accuracy > 60) {
          fixRef.current = null;
          routeOriginRef.current = null;
          setFix(null);
          setRouteOrigin(null);
          setLocationMessage(`Sinal impreciso (±${Math.round(next.accuracy)} m). Aguarde ou escolha uma origem manual.`);
          return;
        }
        if (!shouldAcceptFix(fixRef.current, next)) return;
        fixRef.current = next;
        setFix(next);
        setLocationMessage("");
        if (!routeOriginRef.current || distanceMeters(routeOriginRef.current, next) >= 20) {
          routeOriginRef.current = { lat: next.lat, lng: next.lng };
          setRouteOrigin(routeOriginRef.current);
        }
        if (destinationRef.current && hasArrived(next, destinationRef.current)) {
          setTracking(false);
        }
      },
      (error) => {
        if (!active) return;
        setLocationMessage(errorForLocation(error.code));
        setTracking(false);
        fixRef.current = null;
        routeOriginRef.current = null;
        setFix(null);
        setRouteOrigin(null);
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
    return () => {
      active = false;
      navigator.geolocation.clearWatch(watchId);
    };
  }, [tracking]);

  const campuses = useMemo(() => data?.campuses.filter((item) => item.active) ?? [], [data]);
  const campus = campuses.find((item) => item.id === campusId) ?? campuses[0];
  const buildings = useMemo(
    () => data?.buildings.filter((item) => item.campus_id === campus?.id && item.active) ?? [],
    [data, campus?.id]
  );
  const spaces = useMemo(
    () => data?.spaces.filter((item) => item.campus_id === campus?.id && item.active) ?? [],
    [data, campus?.id]
  );
  const nodes = useMemo(
    () => data?.nodes.filter((item) => item.campus_id === campus?.id) ?? [],
    [data, campus?.id]
  );
  const edges = useMemo(
    () => data?.edges.filter((item) => item.campus_id === campus?.id && item.active) ?? [],
    [data, campus?.id]
  );
  const selectedSpace = destination?.kind === "space"
    ? spaces.find((item) => item.id === destination.id)
    : null;
  const selectedBuilding = destination?.kind === "building"
    ? buildings.find((item) => item.id === destination.id)
    : buildings.find((item) => item.id === selectedSpace?.building_id);
  const entranceNode = selectedBuilding?.entrance_node_id
    ? nodes.find((node) => node.id === selectedBuilding.entrance_node_id)
    : null;
  const entranceGapM = selectedBuilding && entranceNode
    ? distanceMeters(entranceNode, { lat: selectedBuilding.entrance_lat, lng: selectedBuilding.entrance_lng })
    : Number.POSITIVE_INFINITY;
  useEffect(() => {
    destinationRef.current = selectedBuilding ?? null;
  }, [selectedBuilding]);
  const manualBuilding = buildings.find((item) => item.id === manualBuildingId);
  const origin = originMode === "live" ? routeOrigin : manualOrigin;
  const nearestPathDistance = origin && nodes.length > 0
    ? Math.min(...nodes.map((node) => distanceMeters(origin, node)))
    : Number.POSITIVE_INFINITY;
  const route = useMemo(() => {
    if (!campus || !origin || !selectedBuilding) return null;
    return findCampusRoute({
      campusId: campus.id,
      nodes,
      edges,
      origin,
      originNodeId: originMode === "manual" ? manualBuilding?.entrance_node_id : null,
      destination: selectedBuilding,
      accessibleOnly,
    });
  }, [campus, nodes, edges, origin, manualBuilding?.entrance_node_id, originMode, selectedBuilding, accessibleOnly]);
  const arrived = Boolean(selectedBuilding && originMode === "live" && hasArrived(fix, selectedBuilding));

  const filteredBuildings = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("pt-BR");
    if (!query) return buildings;
    return buildings.filter((building) => {
      const matchingSpaces = spaces.filter((space) => space.building_id === building.id);
      return [building.name, building.category, building.description, ...matchingSpaces.flatMap(
        (space) => [space.name, space.kind, space.floor, space.description]
      )].some((value) => value?.toLocaleLowerCase("pt-BR").includes(query));
    });
  }, [buildings, spaces, search]);

  if (!campus) return null;

  const chooseManualBuilding = (id: string) => {
    const building = buildings.find((item) => item.id === id);
    setManualBuildingId(id);
    setManualOrigin(building ? { lat: building.entrance_lat, lng: building.entrance_lng } : null);
    setOriginMode("manual");
    setTracking(false);
    setFix(null);
    setRouteOrigin(null);
    setLocationMessage("");
  };

  const chooseMapOrigin = (point: GeoPoint) => {
    setManualBuildingId("");
    setManualOrigin(point);
    setOriginMode("manual");
    setTracking(false);
    setFix(null);
    setRouteOrigin(null);
    setLocationMessage("Origem marcada no mapa. Escolha um destino para traçar o percurso.");
  };

  const startLocation = () => {
    if (!navigator.geolocation) {
      setLocationMessage("Este navegador não oferece localização. Escolha uma origem no mapa.");
      return;
    }
    fixRef.current = null;
    routeOriginRef.current = null;
    setFix(null);
    setRouteOrigin(null);
    setOriginMode("live");
    setTracking(true);
    setLocationMessage("Aguardando localização do aparelho...");
  };

  const stopLocation = () => {
    setTracking(false);
    setOriginMode("manual");
    fixRef.current = null;
    routeOriginRef.current = null;
    setFix(null);
    setRouteOrigin(null);
    setLocationMessage("Acompanhamento encerrado. Escolha uma origem manual para continuar.");
  };

  return (
    <section className={styles.navigator} aria-label="Navegação geográfica do campus">
      <div className={styles.heading}>
        <div>
          <p>Mapa da instituição</p>
          <h3>Encontre o caminho até a entrada</h3>
        </div>
        {campuses.length > 1 && (
          <label>
            <span>Campus</span>
            <select value={campus.id} onChange={(event) => {
              setCampusId(event.target.value);
              setDestination(null);
              setManualOrigin(null);
              setManualBuildingId("");
              stopLocation();
            }}>
              {campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
        )}
      </div>

      <div className={styles.mapPanel}>
        <CampusMapView
          campus={campus}
          buildings={buildings}
          nodes={nodes}
          edges={edges}
          destinationId={selectedBuilding?.id ?? null}
          route={route}
          fix={originMode === "live" ? fix : null}
          manualOrigin={originMode === "manual" ? manualOrigin : null}
          onSelectBuilding={(id) => setDestination({ kind: "building", id })}
          onSelectManualOrigin={chooseMapOrigin}
        />
        <p className={styles.mapHint}>Toque em um prédio para escolher o destino ou em um caminho para marcar a origem.</p>
      </div>

      <div className={styles.controls}>
        <div className={styles.originControls}>
          <div className={styles.controlTitle}><LocateFixed aria-hidden="true" /><strong>Seu ponto de partida</strong></div>
          <div className={styles.originChoices}>
            <button type="button" onClick={tracking ? stopLocation : startLocation}>
              <LocateFixed aria-hidden="true" /> {tracking ? "Parar acompanhamento" : "Usar minha localização"}
            </button>
            <label>
              <span className={styles.srOnly}>Origem cadastrada</span>
              <select value={manualBuildingId} onChange={(event) => chooseManualBuilding(event.target.value)}>
                <option value="">Escolha uma origem ou toque no mapa</option>
                {buildings.map((building) => <option key={building.id} value={building.id}>{building.name}</option>)}
              </select>
            </label>
          </div>
          {originMode === "live" && fix && <p className={styles.accuracy}>Precisão da localização: ±{Math.round(fix.accuracy)} m</p>}
          {locationMessage && <p className={styles.helper} role="status">{locationMessage}</p>}
        </div>
        <label className={styles.accessibility}>
          <input
            type="checkbox"
            checked={accessibleOnly}
            onChange={(event) => setAccessibleOnly(event.target.checked)}
          />
          <Accessibility aria-hidden="true" /> Usar apenas caminhos acessíveis
        </label>
      </div>

      <div className={styles.destinationHeader}>
        <h4>Escolha o destino</h4>
        <label className={styles.searchField}>
          <Search aria-hidden="true" />
          <span className={styles.srOnly}>Buscar prédio ou espaço</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Busque prédio, auditório ou laboratório" />
        </label>
      </div>
      <div className={styles.buildingList}>
        {filteredBuildings.map((building) => {
          const indoorSpaces = spaces.filter((space) => space.building_id === building.id);
          const selected = selectedBuilding?.id === building.id;
          return (
            <article key={building.id} className={`${styles.buildingCard} ${selected ? styles.buildingCardSelected : ""}`}>
              <button type="button" onClick={() => setDestination({ kind: "building", id: building.id })}>
                <span className={styles.buildingIcon}><Building2 aria-hidden="true" /></span>
                <span><strong>{building.name}</strong><small>{building.category}{building.description ? ` · ${building.description}` : ""}</small></span>
                <MapPin aria-hidden="true" />
              </button>
              {indoorSpaces.length > 0 && (
                <div className={styles.spaces}>
                  {indoorSpaces.map((space) => (
                    <button
                      type="button"
                      key={space.id}
                      className={destination?.kind === "space" && destination.id === space.id ? styles.spaceSelected : ""}
                      onClick={() => setDestination({ kind: "space", id: space.id })}
                    >
                      {space.name}{space.floor ? ` · ${space.floor}` : ""}
                    </button>
                  ))}
                </div>
              )}
            </article>
          );
        })}
        {filteredBuildings.length === 0 && <p className={styles.empty}>Nenhum prédio ou espaço encontrado.</p>}
      </div>

      {selectedBuilding && (
        <div className={styles.routePanel} aria-live="polite">
          <div className={styles.routeTitle}><Navigation aria-hidden="true" /><strong>Destino: {selectedSpace?.name ?? selectedBuilding.name}</strong></div>
          {selectedSpace && <p>{selectedBuilding.name}{selectedSpace.floor ? ` · ${selectedSpace.floor}` : ""}{selectedSpace.description ? ` · ${selectedSpace.description}` : ""}</p>}
          {arrived ? (
            <p className={styles.arrival}>Você chegou à entrada de {selectedBuilding.name}. Consulte a sinalização interna para encontrar o espaço.</p>
          ) : !entranceNode ? (
            <p>A instituição ainda não vinculou a entrada deste prédio a um ponto do caminho.</p>
          ) : entranceGapM > MAX_ENTRANCE_APPROACH_M ? (
            <p>O ponto do caminho vinculado está distante da entrada. Consulte a instituição antes de seguir.</p>
          ) : !origin ? (
            <p>Use sua localização ou escolha uma origem para calcular o percurso.</p>
          ) : !route ? (
            <p>{nearestPathDistance > MAX_PATH_SNAP_M
              ? "Sua origem está longe dos caminhos cadastrados. Aproxime-se do campus ou escolha uma origem no mapa."
              : accessibleOnly
                ? "Não há caminho acessível cadastrado entre esses pontos. Escolha outra origem ou consulte a instituição."
                : "Não há caminho conectado cadastrado entre esses pontos. Escolha outra origem ou consulte a instituição."}</p>
          ) : (
            <>
              <p className={styles.routeMetrics}>{route.distanceM} m · cerca de {Math.max(1, Math.ceil(route.distanceM / 75))} min a pé</p>
              <ol className={styles.steps}>
                {route.startGapM > 8 && <li>Vá até o caminho sinalizado mais próximo (cerca de {Math.round(route.startGapM)} m).</li>}
                {route.nodes.slice(1).map((node, index) => (
                  <li key={node.id}>Siga cerca de {Math.round(route.segmentDistancesM[index])} m até {node.label || "o próximo ponto do caminho"}.</li>
                ))}
                <li>Dirija-se à entrada de {selectedBuilding.name}{route.entranceGapM > 8 ? ` (trecho final estimado de ${Math.round(route.entranceGapM)} m)` : ""}.</li>
              </ol>
              {(route.startGapM > 3 || route.entranceGapM > 3) && (
                <small>Trechos laranja tracejados são apenas uma referência até a rede de caminhos ou a entrada; procure o acesso sinalizado.</small>
              )}
              <small>O percurso usa os caminhos cadastrados pela instituição. Siga sempre a sinalização local.</small>
            </>
          )}
        </div>
      )}
    </section>
  );
}

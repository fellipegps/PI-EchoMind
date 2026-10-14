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

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { MapSelect, mapControlFocus } from "./public-map-controls";

type Destination = { kind: "building" | "space"; id: string } | null;

function errorForLocation(code: number): string {
  if (code === 1) return "A localização foi negada. Escolha uma origem cadastrada ou marque um ponto no mapa.";
  if (code === 2) return "Não foi possível determinar sua posição. Escolha uma origem no mapa.";
  return "A localização demorou a responder. Tente novamente ou escolha uma origem no mapa.";
}

export function PublicCampusNavigator({ publicSlug }: { publicSlug: string }) {
  const [data, setData] = useState<PublicGeoCampus | null>(null);
  const [loadedSlug, setLoadedSlug] = useState<string | null>(null);
  const [error, setError] = useState("");
  const loading = Boolean(publicSlug) && loadedSlug !== publicSlug;
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
      setError("");
      setData(available ? result : null);
    }).catch(() => {
      if (cancelled) return;
      setData(null);
      setError("Não foi possível carregar o mapa do campus agora. Tente novamente mais tarde.");
    }).finally(() => {
      if (!cancelled) setLoadedSlug(publicSlug);
    });
    return () => { cancelled = true; };
  }, [publicSlug]);

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

  if (loading) return <Card role="status" className="p-6 text-sm text-muted-foreground">Carregando mapa do campus…</Card>;
  if (error) return <Card role="alert" className="p-6 text-sm text-destructive">{error}</Card>;
  if (!campus) return <Card role="status" className="gap-2 p-6">
    <h3 className="text-lg font-semibold">Mapa do campus indisponível</h3>
    <p className="text-sm text-muted-foreground">A instituição ainda não disponibilizou um mapa geográfico para consulta.</p>
  </Card>;

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
    <section className="min-w-0 space-y-6 text-foreground [overflow-wrap:anywhere]" aria-label="Navegação geográfica do campus">
      <Card className="min-w-0 gap-6 border-border p-4 sm:p-6">
        <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 space-y-1">
            <p className="text-sm leading-5 font-medium text-primary">Mapa da instituição</p>
            <h3 className="text-xl leading-7 font-semibold tracking-tight">Encontre o caminho até a entrada</h3>
            <p className="text-sm leading-5 text-muted-foreground">{campus.name}</p>
          </div>
          {campuses.length > 1 && <label className="grid min-w-0 gap-2 text-sm font-medium sm:w-64 sm:shrink-0">
            <span>Campus</span>
            <MapSelect value={campus.id} onChange={(event) => {
              setCampusId(event.target.value);
              setDestination(null);
              setManualOrigin(null);
              setManualBuildingId("");
              stopLocation();
            }}>
              {campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </MapSelect>
          </label>}
        </div>

        <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-6 rounded-xl border border-border bg-background p-4">
            <div className="space-y-4">
              <h4 className="flex items-center gap-2 text-base leading-6 font-semibold"><LocateFixed aria-hidden="true" className="size-5 shrink-0 text-primary" />Seu ponto de partida</h4>
              <Button type="button" className={cn("min-h-11 w-full h-auto whitespace-normal", mapControlFocus)} onClick={tracking ? stopLocation : startLocation}>
                <LocateFixed aria-hidden="true" />{tracking ? "Parar acompanhamento" : "Usar minha localização"}
              </Button>
              <label className="grid min-w-0 gap-2 text-sm font-medium">
                <span>Origem cadastrada</span>
                <MapSelect value={manualBuildingId} onChange={(event) => chooseManualBuilding(event.target.value)}>
                  <option value="">Escolha uma origem ou toque no mapa</option>
                  {buildings.map((building) => <option key={building.id} value={building.id}>{building.name}</option>)}
                </MapSelect>
              </label>
              {manualBuilding && originMode === "manual" && <p className="text-sm leading-5 text-muted-foreground">Origem: {manualBuilding.name}</p>}
              {originMode === "live" && fix && <p role="status" className="text-sm leading-5 text-muted-foreground">Precisão da localização: ±{Math.round(fix.accuracy)} m</p>}
              {locationMessage && <p className="text-sm leading-5 text-muted-foreground" role="status">{locationMessage}</p>}
            </div>
            <label className="flex min-h-11 cursor-pointer items-start gap-3 text-sm leading-5">
              <input type="checkbox" checked={accessibleOnly} onChange={(event) => setAccessibleOnly(event.target.checked)}
                className={cn("mt-0.5 size-5 shrink-0 accent-primary outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background", mapControlFocus)} />
              <span className="flex min-w-0 items-start gap-2"><Accessibility aria-hidden="true" className="size-5 shrink-0 text-primary" />Usar apenas caminhos acessíveis</span>
            </label>
          </div>
          <div className="min-w-0 space-y-3">
            <CampusMapView campus={campus} buildings={buildings} nodes={nodes} edges={edges}
              destinationId={selectedBuilding?.id ?? null} route={route}
              fix={originMode === "live" ? fix : null} manualOrigin={originMode === "manual" ? manualOrigin : null}
              onSelectBuilding={(id) => setDestination({ kind: "building", id })} onSelectManualOrigin={chooseMapOrigin} />
            <p className="text-xs leading-4 text-muted-foreground">Toque em um prédio para escolher o destino ou em um caminho para marcar a origem.</p>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <h4 className="text-base leading-6 font-semibold">Escolha o destino</h4>
          <label className="grid min-w-0 gap-2 text-sm font-medium sm:w-80">
            <span>Buscar prédio ou espaço</span>
            <span className="relative block min-w-0"><Search aria-hidden="true" className="pointer-events-none absolute top-3 left-3 size-5 text-muted-foreground" />
              <Input className={cn("h-11 pl-10", mapControlFocus)} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Busque prédio, auditório ou laboratório" />
            </span>
          </label>
        </div>
        <div className="grid min-w-0 gap-4 md:grid-cols-2">
          {filteredBuildings.map((building) => {
            const indoorSpaces = spaces.filter((space) => space.building_id === building.id);
            const selected = selectedBuilding?.id === building.id;
            return <article key={building.id} className={cn("min-w-0 space-y-3 rounded-xl border border-border p-4", selected && "border-primary bg-accent")}>
              <Button type="button" variant="ghost" aria-pressed={selected} aria-label={`${building.name} ${building.category}${building.description ? ` · ${building.description}` : ""}`}
                className={cn("h-auto min-h-11 w-full min-w-0 items-start justify-start gap-3 p-0 text-left whitespace-normal hover:bg-transparent", mapControlFocus)}
                onClick={() => setDestination({ kind: "building", id: building.id })}>
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-primary"><Building2 aria-hidden="true" className="size-5" /></span>
                <span className="min-w-0 flex-1 text-base leading-6 font-semibold">{building.name}</span>
                <MapPin aria-hidden="true" className="mt-1 size-5 shrink-0 text-primary" />
              </Button>
              <p className="text-sm leading-5 text-muted-foreground">{building.category}{building.description ? ` · ${building.description}` : ""}</p>
              {indoorSpaces.length > 0 && <div className="flex min-w-0 flex-wrap gap-2">
                {indoorSpaces.map((space) => <Button type="button" key={space.id} variant="outline"
                  aria-pressed={destination?.kind === "space" && destination.id === space.id}
                  className={cn("h-auto min-h-11 max-w-full whitespace-normal text-left", mapControlFocus, destination?.kind === "space" && destination.id === space.id && "border-primary bg-background text-primary")}
                  onClick={() => setDestination({ kind: "space", id: space.id })}>
                  {space.name}{space.floor ? ` · ${space.floor}` : ""}
                </Button>)}
              </div>}
            </article>;
          })}
          {filteredBuildings.length === 0 && <p role="status" className="col-span-full rounded-xl border border-dashed border-border p-6 text-center text-sm leading-5 text-muted-foreground">Nenhum prédio ou espaço encontrado.</p>}
        </div>
      </Card>

      {selectedBuilding && <Card className="min-w-0 gap-3 border-border p-4 text-sm leading-5 sm:p-6" role="region" aria-live="polite" aria-label="Resumo do percurso">
        <h4 className="flex min-w-0 items-start gap-3 text-base leading-6 font-semibold"><Navigation aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-primary" /><span>Destino: {selectedSpace?.name ?? selectedBuilding.name}</span></h4>
        {selectedSpace && <p>{selectedBuilding.name}{selectedSpace.floor ? ` · ${selectedSpace.floor}` : ""}{selectedSpace.description ? ` · ${selectedSpace.description}` : ""}</p>}
        {arrived ? <p className="font-medium text-success">Você chegou à entrada de {selectedBuilding.name}. Consulte a sinalização interna para encontrar o espaço.</p>
          : !entranceNode ? <p>A instituição ainda não vinculou a entrada deste prédio a um ponto do caminho.</p>
          : entranceGapM > MAX_ENTRANCE_APPROACH_M ? <p>O ponto do caminho vinculado está distante da entrada. Consulte a instituição antes de seguir.</p>
          : !origin ? <p>Use sua localização ou escolha uma origem para calcular o percurso.</p>
          : !route ? <p>{nearestPathDistance > MAX_PATH_SNAP_M
            ? "Sua origem está longe dos caminhos cadastrados. Aproxime-se do campus ou escolha uma origem no mapa."
            : accessibleOnly ? "Não há caminho acessível cadastrado entre esses pontos. Escolha outra origem ou consulte a instituição."
            : "Não há caminho conectado cadastrado entre esses pontos. Escolha outra origem ou consulte a instituição."}</p>
          : <>
            <p className="text-base leading-6 font-semibold text-primary">{route.distanceM} m · cerca de {Math.max(1, Math.ceil(route.distanceM / 75))} min a pé</p>
            <ol className="list-decimal space-y-2 pl-6">
              {route.startGapM > 8 && <li>Vá até o caminho sinalizado mais próximo (cerca de {Math.round(route.startGapM)} m).</li>}
              {route.nodes.slice(1).map((node, index) => <li key={node.id}>Siga cerca de {Math.round(route.segmentDistancesM[index])} m até {node.label || "o próximo ponto do caminho"}.</li>)}
              <li>Dirija-se à entrada de {selectedBuilding.name}{route.entranceGapM > 8 ? ` (trecho final estimado de ${Math.round(route.entranceGapM)} m)` : ""}.</li>
            </ol>
            {(route.startGapM > 3 || route.entranceGapM > 3) && <small className="text-xs leading-4 text-muted-foreground">Trechos tracejados são apenas uma referência até a rede de caminhos ou a entrada; procure o acesso sinalizado.</small>}
            <small className="text-xs leading-4 text-muted-foreground">O percurso usa os caminhos cadastrados pela instituição. Siga sempre a sinalização local.</small>
          </>}
      </Card>}
    </section>
  );
}

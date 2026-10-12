import { Building2, ChevronRight, MapPin, Navigation, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { PublicCampusLocation } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MapSelect, mapControlFocus } from "./public-map-controls";
import styles from "./public-schematic-map.module.css";

type SchematicRoute = { originName: string; destination: PublicCampusLocation; distance: number; minutes: number };

export function PublicSchematicMap({ locations, filteredLocations, loading, error, search, onSearch, originId, onOrigin,
  destinationId, onDestination, originLocation, destinationLocation, route, status, onTrace }: {
  locations: PublicCampusLocation[]; filteredLocations: PublicCampusLocation[]; loading: boolean; error: string;
  search: string; onSearch: (value: string) => void; originId: string; onOrigin: (value: string) => void;
  destinationId: string; onDestination: (location: PublicCampusLocation) => void;
  originLocation: PublicCampusLocation | undefined; destinationLocation: PublicCampusLocation | undefined;
  route: SchematicRoute | null; status: string; onTrace: () => void;
}) {
  return <Card className="min-w-0 gap-6 border-border p-4 text-foreground [overflow-wrap:anywhere] sm:p-6" role="region" aria-label="Navegação esquemática do campus">
    <div className="space-y-1"><h3 className="text-xl leading-7 font-semibold tracking-tight">Mapa esquemático</h3><p className="text-sm leading-5 text-muted-foreground">Estimativa temporária baseada no mapa esquemático.</p></div>
    {loading && <p className="text-sm leading-5 text-muted-foreground" role="status">Carregando locais...</p>}
    {error && <p className="rounded-xl border border-destructive bg-card p-4 text-sm leading-5 text-destructive" role="alert">{error}</p>}
    {!loading && !error && locations.length === 0 && <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">Nenhum local disponível no momento.</p>}
    <div className="grid min-w-0 gap-4 md:grid-cols-2">
      <label className="grid min-w-0 gap-2 text-sm font-medium"><span>Buscar local</span><span className="relative block min-w-0"><Search aria-hidden="true" className="pointer-events-none absolute top-3 left-3 size-5 text-muted-foreground" /><Input className={cn("h-11 pl-10", mapControlFocus)} value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Buscar bloco ou laboratório..." /></span></label>
      <label className="grid min-w-0 gap-2 text-sm font-medium"><span>Ponto de origem</span><MapSelect value={originId} onChange={(event) => onOrigin(event.target.value)}><option value="">Selecione a origem</option>{locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</MapSelect></label>
    </div>
    {originLocation && <p className="text-sm leading-5 text-muted-foreground">Origem: {originLocation.name}</p>}
    <div className={styles.campusMap} aria-label="Mapa esquemático do campus">
      <span className={styles.mapLabel}><Building2 aria-hidden="true" />Campus</span>
      <span className={styles.mapPathOne} aria-hidden="true" /><span className={styles.mapPathTwo} aria-hidden="true" />
      {originLocation && destinationLocation && route && <svg className={styles.routeLine} aria-hidden="true"><line x1={`${originLocation.x}%`} y1={`${originLocation.y}%`} x2={`${destinationLocation.x}%`} y2={`${destinationLocation.y}%`} /></svg>}
      {filteredLocations.map((location) => <button type="button" key={location.id}
        className={cn(styles.mapMarker, mapControlFocus, destinationId === location.id && styles.mapMarkerActive)}
        style={{ left: `${location.x}%`, top: `${location.y}%` }} onClick={() => onDestination(location)}
        aria-pressed={destinationId === location.id} aria-label={`Selecionar ${location.name} como destino`} title={location.name}>
        <MapPin aria-hidden="true" />
      </button>)}
    </div>
    <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="min-w-0 text-sm leading-5 text-muted-foreground" aria-live="polite">{status || "Toque em um marcador para escolher o destino."}</p>
      <Button type="button" className={mapControlFocus} onClick={onTrace} disabled={!originId || !destinationId}><Navigation aria-hidden="true" />Traçar rota</Button>
    </div>
    {route && <div className="flex min-w-0 items-start gap-3 rounded-xl border border-border bg-background p-4" role="status">
      <Navigation aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-primary" />
      <div className="min-w-0 space-y-2"><strong className="block text-base leading-6">{route.originName} → {route.destination.name}</strong><span className="block text-sm leading-5">Aproximadamente {route.distance} m · {route.minutes} min a pé</span><small className="block text-xs leading-4 text-muted-foreground">Estimativa temporária baseada no mapa esquemático.</small></div>
    </div>}
    <div className="grid min-w-0 gap-4 md:grid-cols-2">
      {filteredLocations.map((location) => <article key={location.id} className={cn("min-w-0 space-y-3 rounded-xl border border-border p-4", destinationId === location.id && "border-primary")}>
        <Button type="button" variant="ghost" onClick={() => onDestination(location)} aria-pressed={destinationId === location.id}
          aria-label={`${location.name} ${[location.category, location.building, location.floor].filter(Boolean).join(" · ")}`}
          className={cn("h-auto min-h-11 w-full min-w-0 justify-start gap-3 p-0 text-left whitespace-normal hover:bg-transparent", mapControlFocus)}>
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-primary"><MapPin aria-hidden="true" className="size-5" /></span>
          <span className="min-w-0 flex-1 text-base leading-6 font-semibold">{location.name}</span>
          <ChevronRight aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
        </Button>
        <p className="text-sm leading-5 text-muted-foreground">{[location.category, location.building, location.floor].filter(Boolean).join(" · ")}</p>
      </article>)}
      {!loading && !error && locations.length > 0 && filteredLocations.length === 0 && <p role="status" className="col-span-full rounded-xl border border-dashed border-border p-6 text-center text-sm leading-5 text-muted-foreground">Nenhum local encontrado para essa busca.</p>}
    </div>
  </Card>;
}

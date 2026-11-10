"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, MapPin, Search } from "lucide-react";

import { geoCampusApi, publicPlaceHref } from "@/lib/geocampus-api";
import type { PublicGeoCampus } from "@/lib/geocampus-api";
import { CampusMapView } from "./campus-map-view";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { MapSelect, mapControlFocus } from "./public-map-controls";

export function PublicCampusNavigator({ publicSlug }: { publicSlug: string }) {
  const router = useRouter();
  const [data, setData] = useState<PublicGeoCampus | null>(null);
  const [loadedSlug, setLoadedSlug] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [campusId, setCampusId] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!publicSlug) return;
    let cancelled = false;
    void geoCampusApi.publicMap(publicSlug).then((result) => {
      if (cancelled) return;
      setError("");
      setData(result);
    }).catch(() => {
      if (cancelled) return;
      setData(null);
      setError("Não foi possível carregar o mapa do campus agora. Tente novamente mais tarde.");
    }).finally(() => {
      if (!cancelled) setLoadedSlug(publicSlug);
    });
    return () => { cancelled = true; };
  }, [publicSlug]);

  const currentData = publicSlug && loadedSlug === publicSlug ? data : null;
  const campuses = useMemo(() => currentData?.campuses.filter((item) => item.active) ?? [], [currentData]);
  const campus = campuses.find((item) => item.id === campusId) ?? campuses[0];
  const buildings = useMemo(
    () => currentData?.buildings.filter((item) => item.campus_id === campus?.id && item.active) ?? [],
    [currentData, campus?.id]
  );
  const spaces = useMemo(() => {
    const buildingIds = new Set(buildings.map((item) => item.id));
    return currentData?.spaces.filter((item) => item.active && item.campus_id === campus?.id && buildingIds.has(item.building_id)) ?? [];
  }, [currentData, buildings, campus?.id]);
  const landmarks = useMemo(
    () => currentData?.landmarks.filter((item) => item.campus_id === campus?.id && item.active) ?? [],
    [currentData, campus?.id]
  );
  const query = search.trim().toLocaleLowerCase("pt-BR");
  const filteredBuildings = buildings.filter((building) => {
    const indoorSpaces = spaces.filter((space) => space.building_id === building.id);
    return !query || [building.name, building.category, building.description, ...indoorSpaces.flatMap(
      (space) => [space.name, space.kind, space.floor, space.description]
    )].some((value) => value?.toLocaleLowerCase("pt-BR").includes(query));
  });
  const filteredLandmarks = landmarks.filter((item) => !query || [item.name, item.description]
    .some((value) => value?.toLocaleLowerCase("pt-BR").includes(query)));
  const linkClass = cn("inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4", mapControlFocus);

  if (publicSlug && loadedSlug !== publicSlug) return <Card role="status" className="p-6 text-sm text-muted-foreground">Carregando mapa do campus…</Card>;
  if (error && loadedSlug === publicSlug) return <Card role="alert" className="p-6 text-sm text-destructive">{error}</Card>;
  if (!campus) return <Card role="status" className="gap-2 p-6">
    <h3 className="text-lg font-semibold">Mapa do campus indisponível</h3>
    <p className="text-sm text-muted-foreground">A instituição ainda não disponibilizou um mapa para consulta.</p>
  </Card>;

  return (
    <section className="min-w-0 space-y-6 text-foreground [overflow-wrap:anywhere]" aria-label="Guia visual do campus">
      <Card className="min-w-0 gap-6 border-border p-4 sm:p-6">
        <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 space-y-1">
            <p className="text-sm leading-5 font-medium text-primary">Guia visual da instituição</p>
            <h3 className="text-xl leading-7 font-semibold tracking-tight">Reconheça os locais do campus</h3>
            <p className="text-sm leading-5 text-muted-foreground">{campus.name}</p>
          </div>
          {campuses.length > 1 && <label className="grid min-w-0 gap-2 text-sm font-medium sm:w-64 sm:shrink-0">
            <span>Campus</span>
            <MapSelect value={campus.id} onChange={(event) => { setCampusId(event.target.value); setSearch(""); }}>
              {campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </MapSelect>
          </label>}
        </div>

        <div className="min-w-0 space-y-3">
          <CampusMapView campus={campus} buildings={buildings} landmarks={landmarks}
            onOpenPlace={(type, code) => router.push(publicPlaceHref(publicSlug, type, code))} />
          <p className="text-sm leading-5 text-muted-foreground">Toque em um bloco ou ponto de referência para abrir sua ficha com descrição e fotos. O QR Code afixado no campus abre a mesma ficha.</p>
        </div>

        <label className="grid min-w-0 gap-2 text-sm font-medium">
          <span>Buscar bloco, espaço ou referência</span>
          <span className="relative block min-w-0"><Search aria-hidden="true" className="pointer-events-none absolute top-3 left-3 size-5 text-muted-foreground" />
            <Input className={cn("h-11 pl-10", mapControlFocus)} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Busque bloco, auditório, laboratório ou referência" />
          </span>
        </label>
        <div className="grid min-w-0 gap-4 md:grid-cols-2">
          {filteredBuildings.map((building) => {
            const indoorSpaces = spaces.filter((space) => space.building_id === building.id);
            return <article key={building.id} className="min-w-0 space-y-3 rounded-xl border border-border p-4">
              <h4 className="flex items-start gap-3 text-base font-semibold"><Building2 aria-hidden="true" className="mt-1 size-5 shrink-0 text-primary" />{building.name}</h4>
              {building.description && <p className="text-sm leading-5 text-muted-foreground">{building.description}</p>}
              <Link className={linkClass} href={publicPlaceHref(publicSlug, "building", building.public_code)}>Ver ficha de {building.name}</Link>
              {indoorSpaces.length > 0 && <div className="space-y-2 border-t border-border pt-3">
                <p className="text-sm font-medium">Espaços neste bloco</p>
                <ul className="space-y-1">
                  {indoorSpaces.map((space) => <li key={space.id}>
                    <Link className={linkClass} href={publicPlaceHref(publicSlug, "space", space.public_code)}>
                      {space.name}{space.floor ? ` · ${space.floor}` : ""}
                    </Link>
                  </li>)}
                </ul>
              </div>}
            </article>;
          })}
          {filteredLandmarks.map((landmark) => <article key={landmark.id} className="min-w-0 space-y-3 rounded-xl border border-border p-4">
            <h4 className="flex items-start gap-3 text-base font-semibold"><MapPin aria-hidden="true" className="mt-1 size-5 shrink-0 text-primary" />{landmark.name}</h4>
            <p className="text-sm text-muted-foreground">Ponto de referência</p>
            {landmark.description && <p className="text-sm leading-5 text-muted-foreground">{landmark.description}</p>}
            <Link className={linkClass} href={publicPlaceHref(publicSlug, "landmark", landmark.public_code)}>Ver ficha de {landmark.name}</Link>
          </article>)}
          {filteredBuildings.length === 0 && filteredLandmarks.length === 0 && <p role="status" className="col-span-full rounded-xl border border-dashed border-border p-6 text-center text-sm leading-5 text-muted-foreground">{query ? "Nenhum local encontrado para essa busca." : "A instituição ainda não publicou locais neste campus."}</p>}
        </div>
      </Card>
    </section>
  );
}

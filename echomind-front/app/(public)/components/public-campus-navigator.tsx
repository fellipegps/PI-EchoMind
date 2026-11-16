"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpen, Building2, ChevronRight, MapPin, Trophy } from "lucide-react";

import { geoCampusApi, publicPlaceHref } from "@/lib/geocampus-api";
import type { PublicGeoCampus } from "@/lib/geocampus-api";
import { CampusMapView } from "./campus-map-view";
import { CampusGuideView } from "./campus-guide-view";
import {
  anapolisDestinationHref,
  anapolisDestinations,
  anapolisPublishedPlaces,
  campusModelKey,
  normalizePlaceText,
  type MapPlace,
} from "./campus-guide/places";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { MapSelect, mapControlFocus } from "./public-map-controls";
import styles from "./public-campus-navigator.module.css";

const destinationIcons = { book: BookOpen, sport: Trophy };

export function PublicCampusNavigator({ publicSlug, companyName = "", directoryTarget }: {
  publicSlug: string;
  companyName?: string;
  directoryTarget: HTMLElement | null;
}) {
  const router = useRouter();
  const [data, setData] = useState<PublicGeoCampus | null>(null);
  const [loadedSlug, setLoadedSlug] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [campusId, setCampusId] = useState("");
  const [search, setSearch] = useState("");
  const [focusRequest, setFocusRequest] = useState<{ id: string } | null>(null);
  const [unavailableModel, setUnavailableModel] = useState("");

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
  const campus = campuses.find((item) => item.id === campusId)
    ?? campuses.find((item) => campusModelKey(item, publicSlug, companyName))
    ?? campuses[0];
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
  const modelKey = currentData && campusModelKey(campus, publicSlug, companyName);
  const showAnapolisModel = modelKey === "anapolis";
  const legacyModel = showAnapolisModel && !campus?.model_key;
  const instance = [publicSlug, campus?.id, modelKey].join(":");
  const renderModel = Boolean(modelKey) && unavailableModel !== instance;
  const onModelUnavailable = useCallback(() => setUnavailableModel(instance), [instance]);
  const origin = useMemo<[number, number] | undefined>(() => !showAnapolisModel && campus
    ? [campus.center_lng, campus.center_lat] : undefined, [campus, showAnapolisModel]);
  const placeLinks = useMemo(
    () => Object.fromEntries(anapolisDestinations.map(({ id }) => [id, anapolisDestinationHref(publicSlug, id)])),
    [publicSlug]
  );
  const publishedDestinations = useMemo(() => showAnapolisModel
    ? anapolisPublishedPlaces(legacyModel ? buildings : buildings.filter((building) => building.model_destination_id), [])
    : null, [buildings, legacyModel, showAnapolisModel]);
  const mapPlaces = useMemo<MapPlace[]>(() => {
    const destinationIds = new Map(Array.from(publishedDestinations ?? [], ([id, place]) => [place.id, id]));
    const spacesByBuilding = new Map<string, typeof spaces>();
    for (const space of spaces) {
      const group = spacesByBuilding.get(space.building_id);
      if (group) group.push(space);
      else spacesByBuilding.set(space.building_id, [space]);
    }
    return [
      ...buildings.map((place): MapPlace => {
        const destinationId = showAnapolisModel ? destinationIds.get(place.id) : place.model_destination_id;
        const indoor = spacesByBuilding.get(place.id) ?? [];
        return {
          id: `place-building-${place.public_code}`, name: place.name, description: place.description,
          kind: place.category, photos: place.photos, destinationId,
          coordinates: [place.entrance_lng, place.entrance_lat],
          spaces: (campus?.model_defaults_applied || indoor.length)
            ? indoor.map((space) => ({ ...space,
              href: publicPlaceHref(publicSlug, "space", space.public_code),
            })) : undefined,
          href: (destinationId && placeLinks[destinationId] && showAnapolisModel ? placeLinks[destinationId] : null)
            ?? publicPlaceHref(publicSlug, "building", place.public_code),
        };
      }),
      ...landmarks.map((place): MapPlace => ({
        id: `place-landmark-${place.public_code}`, name: place.name, description: place.description,
        kind: "Ponto de referência", photos: place.photos,
        coordinates: [place.lng, place.lat], href: publicPlaceHref(publicSlug, "landmark", place.public_code),
      })),
    ];
  }, [buildings, campus?.model_defaults_applied, landmarks, placeLinks, publicSlug, publishedDestinations, showAnapolisModel, spaces]);
  const linkedBuildings = new Set(Array.from(publishedDestinations?.values() ?? []).filter((item) => item.type === "building").map((item) => item.id));
  const query = normalizePlaceText(search);
  const spacesFor = (id: string) => spaces.filter((space) => space.building_id === id);
  const searchableSpaces = (id: string) => spacesFor(id).flatMap(
    (space) => [space.name, space.kind, space.floor, space.description]
  );
  const matches = (values: (string | null | undefined)[]) =>
    !query || values.some((value) => value && normalizePlaceText(value).includes(query));
  const filteredDestinations = showAnapolisModel ? anapolisDestinations.filter((destination) => {
    const published = publishedDestinations?.get(destination.id);
    if (!legacyModel && !published) return false;
    if (/^[a-z]\d?$/.test(query)) return normalizePlaceText(destination.shortName) === query;
    return matches([
      published?.name ?? destination.name, destination.kind, destination.shortName,
      ...(published?.type === "building" && campus?.model_defaults_applied ? [] : destination.laboratories ?? []),
      published?.name, published?.description, ...(published?.type === "building" ? searchableSpaces(published.id) : []),
    ]);
  }) : [];
  const filteredBuildings = buildings.filter((building) => !linkedBuildings.has(building.id) &&
    matches([building.name, building.category, building.description, ...searchableSpaces(building.id)]));
  const filteredLandmarks = landmarks.filter((item) => matches([item.name, item.description]));
  const totalDestinations = filteredDestinations.length + filteredBuildings.length + filteredLandmarks.length;
  const linkClass = cn("inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4", mapControlFocus);

  if (publicSlug && loadedSlug !== publicSlug) return <Card role="status" className="mx-4 p-6 text-sm text-muted-foreground sm:mx-6">Carregando mapa do campus…</Card>;
  if (error && loadedSlug === publicSlug) return <Card role="alert" className="mx-4 p-6 text-sm text-destructive sm:mx-6">{error}</Card>;
  if (!campus && !showAnapolisModel) return <Card role="status" className="mx-4 gap-2 p-6 sm:mx-6">
    <h3 className="text-lg font-semibold">Mapa do campus indisponível</h3>
    <p className="text-sm text-muted-foreground">A instituição ainda não disponibilizou um mapa para consulta.</p>
  </Card>;

  const directory = (
      <aside className={styles.directory} aria-label="Destinos do campus">
        <div className={styles.searchPanel}>
          <p className={styles.campusName}>{showAnapolisModel ? "Campus Anápolis · Setor leste" : campus?.name}</p>
          {!showAnapolisModel && <h3 className="text-base font-semibold">Reconheça os locais do campus</h3>}
          {campus && campuses.length > 1 && <label className="grid min-w-0 gap-2 text-sm font-medium">
            <span>Campus</span>
            <MapSelect value={campus.id} onChange={(event) => { setCampusId(event.target.value); setSearch(""); setFocusRequest(null); }}>
              {campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </MapSelect>
          </label>}
          <label className="grid min-w-0 gap-1.5 text-sm font-semibold">
            <span>Buscar no campus</span>
            <Input type="search" className={cn(styles.searchInput, mapControlFocus)}
              value={search} onChange={(event) => setSearch(event.target.value)}
              placeholder="Bloco ou laboratório…" aria-controls="campus-destinations" />
          </label>
          {totalDestinations > 0 && <p role="status" className={styles.count}>
            {totalDestinations} {totalDestinations === 1 ? "destino" : "destinos"}
          </p>}
        </div>
        <div id="campus-destinations" className={styles.destinations}>
          {filteredDestinations.map((destination) => {
            const Icon = destination.icon === "book" || destination.icon === "sport"
              ? destinationIcons[destination.icon] : Building2;
            const place = publishedDestinations?.get(destination.id);
              const name = place?.name ?? destination.name;
            const matchingSpaces = query && place?.type === "building"
              ? spacesFor(place.id).filter((space) => matches([space.name, space.kind, space.floor, space.description]))
              : [];
            return <article key={destination.id} className={styles.destination}>
              <Link className={cn(styles.destinationLink, mapControlFocus)} href={placeLinks[destination.id]}
                aria-label={`Ver ficha de ${name}`}>
                <span className={styles.destinationIcon}><Icon aria-hidden="true" className="size-5" /></span>
                <span>
                  <strong>{name}</strong>
                  <small>{destination.kind}</small>
                </span>
                <ChevronRight aria-hidden="true" className="size-4" />
              </Link>
              {matchingSpaces.length > 0 && <ul className="border-t border-border px-3" aria-label="Espaços encontrados">
                {matchingSpaces.map((space) => <li key={space.id}>
                  <Link className={linkClass} href={publicPlaceHref(publicSlug, "space", space.public_code)}>
                    {space.name}{space.floor ? ` · ${space.floor}` : ""}
                  </Link>
                </li>)}
              </ul>}
            </article>;
          })}
          {filteredBuildings.map((building) => {
            const indoorSpaces = spacesFor(building.id);
            return <article key={building.id} className={cn(styles.publishedDestination, "min-w-0 space-y-3 rounded-xl border border-border p-4")}>
              <h4 className="flex items-start gap-3 text-base font-semibold"><Building2 aria-hidden="true" className="mt-1 size-5 shrink-0 text-primary" />{building.name}</h4>
              {building.description && <p className="text-sm leading-5 text-muted-foreground">{building.description}</p>}
              <Link className={linkClass} href={publicPlaceHref(publicSlug, "building", building.public_code)}>Ver ficha de {building.name}</Link>
              {renderModel && <button className={cn(linkClass, "ml-3")} type="button" aria-label={`Ver no mapa: ${building.name}`}
                onClick={() => setFocusRequest({ id: `place-building-${building.public_code}` })}>Ver no mapa</button>}
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
          {filteredLandmarks.map((landmark) => <article key={landmark.id} className={cn(styles.publishedDestination, "min-w-0 space-y-3 rounded-xl border border-border p-4")}>
            <h4 className="flex items-start gap-3 text-base font-semibold"><MapPin aria-hidden="true" className="mt-1 size-5 shrink-0 text-primary" />{landmark.name}</h4>
            <p className="text-sm text-muted-foreground">Ponto de referência</p>
            {landmark.description && <p className="text-sm leading-5 text-muted-foreground">{landmark.description}</p>}
            <Link className={linkClass} href={publicPlaceHref(publicSlug, "landmark", landmark.public_code)}>Ver ficha de {landmark.name}</Link>
            {renderModel && <button className={cn(linkClass, "ml-3")} type="button" aria-label={`Ver no mapa: ${landmark.name}`}
              onClick={() => setFocusRequest({ id: `place-landmark-${landmark.public_code}` })}>Ver no mapa</button>}
          </article>)}
          {totalDestinations === 0 && <p role="status" className="py-2 text-sm text-muted-foreground">{query ? "Nenhum local encontrado para essa busca." : "A instituição ainda não publicou locais neste campus."}</p>}
        </div>
      </aside>
  );

  return (
    <section className={styles.mapPane} aria-label="Guia visual do campus">
      {directoryTarget && createPortal(directory, directoryTarget)}
      {modelKey && renderModel ? <CampusGuideView key={instance} modelKey={modelKey} origin={origin} placeLinks={placeLinks}
        places={mapPlaces} showUnlinked={legacyModel} focusRequest={focusRequest} onUnavailable={onModelUnavailable} />
        : campus && <CampusMapView campus={campus} buildings={buildings} landmarks={landmarks}
          onOpenPlace={(type, code) => router.push(publicPlaceHref(publicSlug, type, code))} />}
    </section>
  );
}

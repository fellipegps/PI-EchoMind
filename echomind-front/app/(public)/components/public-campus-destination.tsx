"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, MapPin } from "lucide-react";
import { EchoMindBrand } from "@/components/echomind-brand";
import { publicPortalApi } from "@/lib/api";
import { geoCampusApi, publicPlaceHref, type PublicGeoCampus } from "@/lib/geocampus-api";
import {
  anapolisDestinationSources,
  anapolisPublishedPlaces,
  campusModelKey,
  type AnapolisDestination,
} from "./campus-guide/places";
import { PublicCampusPhotos } from "./public-campus-place";

export function PublicCampusDestination({ publicSlug, destination }: {
  publicSlug: string;
  destination: AnapolisDestination;
}) {
  const [result, setResult] = useState<{
    slug: string;
    companyName: string | null;
    map: PublicGeoCampus | null;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      publicPortalApi.getInstitution(publicSlug),
      geoCampusApi.publicMap(publicSlug).catch(() => null),
    ]).then(([institution, map]) => {
      if (!cancelled) setResult({ slug: publicSlug, companyName: institution.company_name ?? "", map });
    }).catch(() => {
      if (!cancelled) setResult({ slug: publicSlug, companyName: null, map: null });
    });
    return () => { cancelled = true; };
  }, [publicSlug]);

  const loaded = result?.slug === publicSlug;
  const campuses = result?.map?.campuses.filter((campus) => campus.active) ?? [];
  const campus = campuses.find((item) => campusModelKey(item, publicSlug, result?.companyName ?? "") === "anapolis");
  const published = campus && anapolisPublishedPlaces(
    result?.map?.buildings.filter((item) => item.active && item.campus_id === campus.id && (!campus.model_key || item.model_destination_id)) ?? [],
    campus.model_key ? [] : result?.map?.landmarks.filter((item) => item.active && item.campus_id === campus.id) ?? [],
  ).get(destination.id);
  const available = loaded && result.companyName !== null && campus && (!campus.model_key || published);
  const spaces = published?.type === "building"
    ? result?.map?.spaces.filter((space) => space.active && space.campus_id === campus?.id && space.building_id === published.id)
    : undefined;
  const sources = anapolisDestinationSources(destination);
  const accessStatus = destination.entry.status === "confirmed" ? "Entrada confirmada"
    : destination.entry.coordinates ? "Entrada a confirmar · ponto demonstrativo" : "Entrada a confirmar";
  const returnHref = `/p/${encodeURIComponent(publicSlug)}?tab=locais`;
  const linkClass = "inline-flex min-h-11 items-center gap-2 rounded-sm text-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4";

  return <main className="min-h-svh bg-background px-4 py-6 text-foreground sm:px-6">
    <div className="mx-auto max-w-4xl space-y-7 [overflow-wrap:anywhere]">
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border pb-4">
        <EchoMindBrand className="text-xl" />
        <Link href={returnHref} className={linkClass}>
          <ArrowLeft aria-hidden="true" className="size-4" />Voltar aos locais do campus
        </Link>
      </header>

      {!loaded ? <p role="status" className="text-muted-foreground">Carregando ficha do local.</p>
        : !available ? <p role="alert" className="text-muted-foreground">Esta ficha está indisponível neste portal.</p>
        : <>
          <div className="space-y-2">
            <p className="flex items-center gap-2 text-sm font-medium text-primary">
              <MapPin aria-hidden="true" className="size-4" />Campus Anápolis · Setor leste
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">{published?.name ?? destination.name}</h1>
            <p className="text-muted-foreground">{destination.kind}</p>
          </div>

          {destination.laboratories?.length && !spaces?.length && !campus?.model_defaults_applied ? <section aria-labelledby="destination-labs" className="space-y-3">
            <h2 id="destination-labs" className="text-xl font-semibold">Laboratórios</h2>
            <ul className="list-disc space-y-2 pl-6">
              {destination.laboratories.map((lab) => <li key={lab}>{lab}</li>)}
            </ul>
          </section> : null}

          <section aria-labelledby="destination-access" className="space-y-2 border-t border-border pt-5">
            <h2 id="destination-access" className="text-xl font-semibold">Referência de acesso</h2>
            <p className="text-sm font-medium text-muted-foreground">{accessStatus}</p>
            <p className="leading-relaxed">{destination.entry.description}</p>
            {destination.photoNote && <p className="text-sm text-muted-foreground">{destination.photoNote}</p>}
          </section>

          {published && <section aria-labelledby="destination-published" className="space-y-2 border-t border-border pt-5">
            <h2 id="destination-published" className="text-xl font-semibold">Cadastro da instituição</h2>
            {published.description && <p className="whitespace-pre-wrap leading-relaxed">{published.description}</p>}
            <Link href={publicPlaceHref(publicSlug, published.type, published.public_code)} className={linkClass}>
              Ver cadastro e fotos de {published.name}
            </Link>
            {spaces?.length ? <ul aria-label="Espaços internos">
              {spaces.map((space) => <li key={space.id}>
                <Link href={publicPlaceHref(publicSlug, "space", space.public_code)} className={linkClass}>
                  {space.name}{space.floor ? ` · ${space.floor}` : ""}
                </Link>
                {space.description && <p className="text-sm text-muted-foreground">{space.description}</p>}
              </li>)}
            </ul> : null}
          </section>}

          {published?.photos.length ? <PublicCampusPhotos photos={published.photos} name={published.name} /> : null}

          <details className="border-t border-border pt-4">
            <summary className="cursor-pointer py-2 font-medium">Fontes da maquete</summary>
            <ul>
              {sources.map((source) => <li key={source.url}>
                <a href={source.url} target="_blank" rel="noopener noreferrer" className={linkClass}>{source.label}</a>
              </li>)}
            </ul>
          </details>
        </>}
    </div>
  </main>;
}

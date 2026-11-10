"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, Building2, Camera, MapPin } from "lucide-react";

import { campusPhotoUrl, geoCampusApi, publicPlaceHref } from "@/lib/geocampus-api";
import type { PlacePhoto, PlaceType, PublicPlace } from "@/lib/geocampus-api";
import { EchoMindBrand } from "@/components/echomind-brand";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

function ReferencePhoto({ photo, name, index }: { photo: PlacePhoto; name: string; index: number }) {
  const [failed, setFailed] = useState(false);
  return <figure className="min-w-0 overflow-hidden rounded-xl border border-border bg-card">
    {failed ? <p role="status" className="p-6 text-sm text-muted-foreground">Esta foto está indisponível no momento.</p>
      : <Image src={campusPhotoUrl(photo.url)} alt={photo.caption || `${name}, foto de referência ${index + 1}`}
          width={1200} height={900} unoptimized className="h-auto max-h-[560px] w-full object-contain"
          onError={() => setFailed(true)} />}
    {photo.caption && <figcaption className="px-4 py-3 text-sm text-muted-foreground">{photo.caption}</figcaption>}
  </figure>;
}

export function PublicCampusPlace({ publicSlug, type, publicCode }: {
  publicSlug: string;
  type: PlaceType;
  publicCode: string;
}) {
  const [data, setData] = useState<PublicPlace | null>(null);
  const [loadedKey, setLoadedKey] = useState("");
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${publicSlug}/${type}/${publicCode}/${attempt}`;

  useEffect(() => {
    let cancelled = false;
    void geoCampusApi.publicPlace(publicSlug, type, publicCode).then((result) => {
      if (!cancelled) setData(result);
    }).catch(() => { if (!cancelled) setData(null); }).finally(() => {
      if (!cancelled) setLoadedKey(requestKey);
    });
    return () => { cancelled = true; };
  }, [publicSlug, type, publicCode, requestKey]);

  const loaded = loadedKey === requestKey;
  const place = loaded ? data?.place : null;
  const building = loaded ? data?.building : null;
  const photos = [...(place?.photos ?? [])].sort((left, right) => left.sort_order - right.sort_order);
  const kindLabel = type === "building" ? "Bloco ou prédio" : type === "space" ? "Espaço interno" : "Ponto de referência";

  return <main className="min-h-svh bg-background px-4 py-6 text-foreground sm:px-6 [overflow-wrap:anywhere]">
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
        <EchoMindBrand className="text-xl" />
        <Link href={`/p/${encodeURIComponent(publicSlug)}?tab=locais`} className="inline-flex min-h-11 items-center gap-2 rounded text-sm text-primary underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4">
          <ArrowLeft aria-hidden="true" className="size-4" />Voltar aos locais do campus
        </Link>
      </header>
      {!loaded ? <Card role="status" className="p-6">Carregando informações do local…</Card>
        : !place || !data ? <Card className="gap-4 p-6">
          <h1 className="text-2xl font-semibold">Local indisponível</h1>
          <p role="alert" className="text-sm text-muted-foreground">Não foi possível abrir esta ficha. Confira o endereço ou o QR Code com a instituição e tente novamente.</p>
          <Button type="button" className="w-fit" onClick={() => setAttempt((value) => value + 1)}>Tentar novamente</Button>
        </Card>
        : <>
          <Card className="gap-4 p-5 sm:p-6">
            <p className="flex items-center gap-2 text-sm font-medium text-primary"><MapPin aria-hidden="true" className="size-4" />{data.campus.name} · {kindLabel}</p>
            <h1 className="text-3xl font-semibold tracking-tight">{place.name}</h1>
            {building && <p className="flex flex-wrap items-center gap-2 text-sm"><Building2 aria-hidden="true" className="size-4" />Fica no bloco <Link href={publicPlaceHref(publicSlug, "building", building.public_code)} className="inline-flex min-h-11 items-center rounded font-medium text-primary underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4">{building.name}</Link></p>}
            {"floor" in place && place.floor && <p className="text-sm text-muted-foreground">Andar · {place.floor}</p>}
            {place.description && <p className="whitespace-pre-wrap leading-relaxed">{place.description}</p>}
          </Card>
          <section aria-labelledby="reference-photos-title" className="space-y-4">
            <h2 id="reference-photos-title" className="flex items-center gap-2 text-xl font-semibold"><Camera aria-hidden="true" className="size-5" />Fotos de referência</h2>
            {photos.length > 0 ? <div className="grid min-w-0 gap-4 sm:grid-cols-2">
              {photos.map((photo, index) => <ReferencePhoto key={`${photo.id}:${photo.url}`} photo={photo} name={place.name} index={index} />)}
            </div> : <Card className="p-6 text-sm text-muted-foreground">A instituição ainda não publicou fotos deste local.</Card>}
          </section>
        </>}
    </div>
  </main>;
}

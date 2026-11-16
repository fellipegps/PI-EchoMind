"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Camera, Loader2, MapPin, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { configApi } from "@/lib/api";
import { geoCampusApi, publicPlaceHref, type Building, type Campus, type IndoorSpace, type Landmark, type PlaceType } from "@/lib/geocampus-api";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { GeoCampusMap, type GeoPoint } from "./geo-campus-map";
import { PlaceMediaManager } from "./place-media-manager";
import { PlaceQrCode } from "./place-qr-code";
import { CampusBuildingManager } from "./campus-building-manager";
import { CampusGuideView } from "../../(public)/components/campus-guide-view";
import { campusModelKey, type MapPlace } from "../../(public)/components/campus-guide/places";

const emptyForm = { name: "", description: "", lat: "", lng: "", active: true };
const noPlaceLinks = {};

function pointFromForm({ lat, lng }: typeof emptyForm): GeoPoint | null {
  const point = { lat: Number(lat), lng: Number(lng) };
  return lat.trim() && lng.trim() && Math.abs(point.lat) <= 90 && Math.abs(point.lng) <= 180 ? point : null;
}

export function GeoCampusManager() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [campusId, setCampusId] = useState("");
  const [publicSlug, setPublicSlug] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [loadingCampuses, setLoadingCampuses] = useState(true);
  const [campusError, setCampusError] = useState(false);
  const [map, setMap] = useState<{ campusId: string; buildings: Building[]; spaces: IndoorSpace[]; landmarks: Landmark[] }>();
  const [mapError, setMapError] = useState("");
  const [editor, setEditor] = useState<{ id?: string } | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [focusPoint, setFocusPoint] = useState<GeoPoint | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Landmark | null>(null);
  const [removing, setRemoving] = useState(false);
  const [mediaId, setMediaId] = useState("");
  const [buildingId, setBuildingId] = useState("");
  const [unavailableModel, setUnavailableModel] = useState("");
  const mapRequest = useRef(0);
  const selectedCampus = useRef("");
  const preparedCampuses = useRef(new Set<string>());
  const editorHeading = useRef<HTMLHeadingElement>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);
  const newPointButton = useRef<HTMLButtonElement>(null);
  const deleteTrigger = useRef<HTMLButtonElement | null>(null);
  const mediaHeading = useRef<HTMLHeadingElement>(null);

  const campus = campuses.find((item) => item.id === campusId);
  const campusMap = map?.campusId === campusId ? map : undefined;
  const modelKey = campusModelKey(campus, publicSlug, companyName);
  const shouldPrepareModel = modelKey === "anapolis" && !campus?.model_defaults_applied;
  const origin = useMemo<[number, number] | undefined>(() => campus && modelKey !== "anapolis"
    ? [campus.center_lng, campus.center_lat] : undefined, [campus, modelKey]);
  const onModelUnavailable = useCallback(() => setUnavailableModel(campusId), [campusId]);
  const mapPlaces = useMemo<MapPlace[]>(() => {
    if (!campusMap) return [];
    const placeHref = (type: PlaceType, code: string) => publicSlug ? publicPlaceHref(publicSlug, type, code) : "";
    const photosFor = (type: PlaceType, item: Building | Landmark) => !publicSlug || !item.active ? [] : item.photos.map((photo) => ({
      ...photo, url: `/public/${encodeURIComponent(publicSlug)}/places/${type}/${encodeURIComponent(item.public_code)}/photos/${encodeURIComponent(photo.id)}`,
    }));
    return [
      ...campusMap.buildings.map((item): MapPlace => ({
        ...item, id: `building:${item.id}`, kind: item.category, destinationId: item.model_destination_id,
        coordinates: [item.entrance_lng, item.entrance_lat], photos: photosFor("building", item),
        href: item.active ? placeHref("building", item.public_code) : "",
        spaces: campusMap.spaces.filter((space) => space.building_id === item.id).map((space) => ({
          ...space, href: space.active && item.active ? placeHref("space", space.public_code) : "",
        })),
      })),
      ...campusMap.landmarks.map((item): MapPlace => ({
        ...item, id: `landmark:${item.id}`, kind: "Ponto de referência", coordinates: [item.lng, item.lat],
        photos: photosFor("landmark", item), href: item.active ? placeHref("landmark", item.public_code) : "",
      })),
    ];
  }, [campusMap, publicSlug]);
  const manageMapPlace = useCallback((id: string) => {
    if (id.startsWith("building:")) {
      setBuildingId(id.slice("building:".length));
      document.getElementById("campus-building-manager")?.scrollIntoView?.({ block: "start" });
      document.getElementById("campus-building-select")?.focus({ preventScroll: true });
    } else if (id.startsWith("landmark:")) {
      setMediaId(id.slice("landmark:".length));
    }
  }, []);
  const media = campusMap?.landmarks.find((item) => item.id === mediaId);
  const draftPoint = editor ? pointFromForm(form) : null;

  useEffect(() => {
    let active = true;
    void Promise.all([geoCampusApi.campuses.list(), configApi.get().catch(() => null)]).then(([items, config]) => {
      if (!active) return;
      const published = items.filter((item) => item.active);
      setCampuses(published);
      setPublicSlug(config?.public_slug ?? "");
      setCompanyName(config?.company_name ?? "");
      selectedCampus.current = published[0]?.id ?? "";
      setCampusId(selectedCampus.current);
    }).catch(() => { if (active) setCampusError(true); })
      .finally(() => { if (active) setLoadingCampuses(false); });
    return () => { active = false; };
  }, []);

  const loadMap = useCallback(async (id: string, prepare = false) => {
    const request = ++mapRequest.current;
    try {
      const structure = async () => {
        if (prepare && !preparedCampuses.current.has(id)) {
          await geoCampusApi.campuses.prepareModel(id);
          preparedCampuses.current.add(id);
        }
        return Promise.all([geoCampusApi.buildings.list(id), geoCampusApi.spaces.list(id)]);
      };
      const [[buildings, spaces], landmarks] = await Promise.all([structure(), geoCampusApi.landmarks.list(id)]);
      if (mapRequest.current !== request) return;
      setMap({ campusId: id, buildings, spaces, landmarks });
      setMapError("");
    } catch (error) {
      if (mapRequest.current === request) setMapError("Não foi possível carregar os dados deste campus.");
      throw error;
    }
  }, []);

  useEffect(() => {
    if (!campusId) return;
    void loadMap(campusId, shouldPrepareModel).catch(() => {});
    return () => { mapRequest.current += 1; };
  }, [campusId, loadMap, shouldPrepareModel]);

  useEffect(() => {
    if (editor) editorHeading.current?.focus();
    else if (editorTrigger.current) {
      (editorTrigger.current.isConnected ? editorTrigger.current : newPointButton.current)?.focus();
      editorTrigger.current = null;
    }
  }, [editor]);
  useEffect(() => { if (mediaId) mediaHeading.current?.focus(); }, [mediaId]);

  function selectCampus(id: string) {
    mapRequest.current += 1;
    selectedCampus.current = id;
    setCampusId(id);
    setMap(undefined);
    setMapError("");
    editorTrigger.current = null;
    setEditor(null);
    setFocusPoint(null);
    setMediaId("");
    setBuildingId("");
    setUnavailableModel("");
  }

  function openEditor(landmark?: Landmark) {
    editorTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setEditor({ id: landmark?.id });
    setForm(landmark ? {
      name: landmark.name, description: landmark.description ?? "",
      lat: String(landmark.lat), lng: String(landmark.lng), active: landmark.active,
    } : emptyForm);
    setFocusPoint(landmark ? { lat: landmark.lat, lng: landmark.lng } : null);
  }

  function closeEditor() {
    setEditor(null);
    setFocusPoint(null);
  }

  function pickPoint(point: GeoPoint) {
    setForm((current) => ({ ...current, lat: point.lat.toFixed(7), lng: point.lng.toFixed(7) }));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!campusMap || !editor || saving) return;
    const point = pointFromForm(form);
    const name = form.name.trim();
    if (name.length < 2 || !point) {
      toast.error("Informe um nome com pelo menos dois caracteres e marque um ponto válido.");
      return;
    }
    setSaving(true);
    try {
      const payload = { ...point, name, description: form.description.trim() || null, active: form.active };
      const saved = editor.id
        ? await geoCampusApi.landmarks.update(campusId, editor.id, payload)
        : await geoCampusApi.landmarks.create(campusId, payload);
      setMap((current) => current?.campusId === campusId ? {
        ...current, landmarks: [...current.landmarks.filter((item) => item.id !== saved.id), saved]
          .sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
      } : current);
      void loadMap(campusId).catch(() => {});
      closeEditor();
      if (!editor.id) setMediaId(saved.id);
      toast.success(editor.id ? "Ponto atualizado." : "Ponto cadastrado.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Não foi possível salvar o ponto.");
    } finally { setSaving(false); }
  }

  async function remove() {
    if (!deleteTarget || removing) return;
    setRemoving(true);
    try {
      await geoCampusApi.landmarks.delete(deleteTarget.campus_id, deleteTarget.id);
      setMap((current) => current?.campusId === deleteTarget.campus_id ? {
        ...current, landmarks: current.landmarks.filter((item) => item.id !== deleteTarget.id),
      } : current);
      void loadMap(deleteTarget.campus_id).catch(() => {});
      if (editor?.id === deleteTarget.id) closeEditor();
      if (mediaId === deleteTarget.id) setMediaId("");
      setDeleteTarget(null);
      toast.success("Ponto excluído.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Não foi possível excluir o ponto.");
    } finally { setRemoving(false); }
  }

  return <section className="min-w-0 space-y-6" aria-label="Mapa dos campi">
    <Card><CardContent className="flex flex-wrap items-end gap-4">
      {campus && <div className="min-w-0 flex-1 space-y-2">
        <Label htmlFor="campus-select">Campus</Label>
        <select id="campus-select" className="min-h-11 w-full rounded-lg border border-input bg-card px-3 text-sm"
          value={campusId} onChange={(event) => selectCampus(event.target.value)} disabled={saving || removing}>
          {campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </div>}
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">A equipe EchoMind configura os campi e as geometrias da maquete.</p>
        <Link href="/privacidade#contato-equipe" className="text-sm font-medium text-primary underline underline-offset-4">
          Falar com a equipe EchoMind
        </Link>
      </div>
    </CardContent></Card>

    {loadingCampuses && <p role="status">Carregando campi...</p>}
    {campusError && <p role="alert">Não foi possível carregar os campi. Atualize a página para tentar novamente.</p>}
    {!loadingCampuses && !campusError && !campus && <p role="status">Nenhum campus publicado. Entre em contato com a equipe para configurar o seu.</p>}
    {mapError && <div role="alert" className="flex flex-wrap items-center gap-3">{mapError}
      <Button variant="outline" onClick={() => void loadMap(campusId, shouldPrepareModel).catch(() => {})}>Tentar novamente</Button>
    </div>}
    {campus && !campusMap && !mapError && <p role="status">Carregando pontos...</p>}

    {campus && campusMap && <Card>
      <CardHeader><CardTitle>Mapa e pontos de referência</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <p id="geo-map-instructions" className="text-sm text-muted-foreground">
          {editor ? "Clique no mapa ou arraste o marcador para escolher a posição." : "Selecione Novo ponto para marcar uma referência."}
        </p>
        {modelKey && unavailableModel !== campus.id && <div hidden={Boolean(editor)}>
          <CampusGuideView key={campus.id} modelKey={modelKey} origin={origin} places={mapPlaces} placeLinks={noPlaceLinks}
            showUnlinked={false} focusRequest={null} onUnavailable={onModelUnavailable} onManagePlace={manageMapPlace} />
        </div>}
        {(editor || !modelKey || unavailableModel === campus.id) && <GeoCampusMap key={campus.id}
          center={{ lat: campus.center_lat, lng: campus.center_lng }} zoom={campus.zoom}
          landmarks={campusMap.landmarks} draftPoint={draftPoint} focusPoint={focusPoint}
          onPickPoint={editor && !saving ? pickPoint : undefined} />}
        {!editor && <Button ref={newPointButton} onClick={() => openEditor()}><Plus aria-hidden="true" />Novo ponto</Button>}
        {editor && <form onSubmit={(event) => void save(event)} className="space-y-4 rounded-lg border p-4">
          <h2 ref={editorHeading} tabIndex={-1} className="font-semibold">{editor.id ? "Editar ponto" : "Novo ponto"}</h2>
          <div className="space-y-2"><Label htmlFor="point-name">Nome</Label><Input id="point-name" required minLength={2} maxLength={200} value={form.name}
            disabled={saving} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
          <div className="space-y-2"><Label htmlFor="point-description">Descrição</Label><Textarea id="point-description" maxLength={2000} value={form.description}
            disabled={saving} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="point-lat">Latitude</Label><Input id="point-lat" type="number" step="any" min={-90} max={90} value={form.lat}
              disabled={saving} onChange={(event) => setForm({ ...form, lat: event.target.value })} /></div>
            <div className="space-y-2"><Label htmlFor="point-lng">Longitude</Label><Input id="point-lng" type="number" step="any" min={-180} max={180} value={form.lng}
              disabled={saving} onChange={(event) => setForm({ ...form, lng: event.target.value })} /></div>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} disabled={saving}
            onChange={(event) => setForm({ ...form, active: event.target.checked })} />Visível no mapa público</label>
          <div className="flex flex-wrap gap-2"><Button type="submit" disabled={saving}>{saving && <Loader2 className="animate-spin" />}Salvar ponto</Button>
            <Button type="button" variant="outline" onClick={closeEditor} disabled={saving}>Cancelar</Button></div>
        </form>}
        {!campusMap.landmarks.length && <p className="text-sm text-muted-foreground">Nenhum ponto de referência cadastrado.</p>}
        <div className="grid gap-3 lg:grid-cols-2">
          {campusMap.landmarks.map((point) => <article key={point.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
            <div className="min-w-0"><h3 className="flex items-center gap-2 break-words font-medium"><MapPin aria-hidden="true" className="size-4 shrink-0" />{point.name}</h3>
              {!point.active && <Badge variant="secondary">Oculto</Badge>}
              <p className="text-sm text-muted-foreground">{point.photos.length} foto(s)</p></div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => setMediaId(point.id)} aria-label={"Fotos e QR Code de " + point.name}><Camera aria-hidden="true" />Fotos e QR Code</Button>
              <Button size="icon" variant="outline" disabled={saving || removing} onClick={() => openEditor(point)} aria-label={"Editar " + point.name}><Pencil aria-hidden="true" /></Button>
              <Button size="icon" variant="outline" disabled={saving || removing} onClick={(event) => {
                deleteTrigger.current = event.currentTarget;
                setDeleteTarget(point);
              }} aria-label={"Excluir " + point.name}><Trash2 aria-hidden="true" /></Button>
            </div>
          </article>)}
        </div>
      </CardContent>
    </Card>}

    {campus && campusMap && <CampusBuildingManager buildings={campusMap.buildings} spaces={campusMap.spaces}
      buildingId={buildingId} onSelect={setBuildingId} publicSlug={publicSlug} onChanged={async () => {
        if (selectedCampus.current === campus.id) await loadMap(campus.id);
      }} />}

    {campus && media && <Card>
      <CardHeader><CardTitle><h2 ref={mediaHeading} tabIndex={-1}>Fotos e QR Code de {media.name}</h2></CardTitle></CardHeader>
      <CardContent className="grid items-start gap-4 lg:grid-cols-2">
        <PlaceMediaManager key={media.id} campusId={campus.id} placeType="landmark" placeId={media.id}
          placeName={media.name} photos={media.photos} onChanged={async () => {
            if (selectedCampus.current === campus.id) await loadMap(campus.id);
          }} />
        <PlaceQrCode key={media.public_code} publicSlug={publicSlug} placeType="landmark" publicCode={media.public_code} placeName={media.name} />
      </CardContent>
    </Card>}
    <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open && !removing) setDeleteTarget(null); }}>
      <AlertDialogContent onCloseAutoFocus={(event) => {
        event.preventDefault();
        (deleteTrigger.current?.isConnected ? deleteTrigger.current : newPointButton.current)?.focus();
      }}>
        <AlertDialogHeader><AlertDialogTitle>Excluir {deleteTarget?.name}?</AlertDialogTitle>
          <AlertDialogDescription>O ponto e suas fotos serão removidos do guia público.</AlertDialogDescription></AlertDialogHeader>
        <AlertDialogFooter><AlertDialogCancel disabled={removing}>Cancelar</AlertDialogCancel>
          <AlertDialogAction disabled={removing} onClick={(event) => { event.preventDefault(); void remove(); }}>Excluir</AlertDialogAction></AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </section>;
}

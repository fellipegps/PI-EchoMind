"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Building2, Camera, Loader2, MapPin, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { configApi } from "@/lib/api";
import {
  geoCampusApi,
  type Building,
  type BuildingInput,
  type Campus,
  type CampusInput,
  type IndoorSpace,
  type IndoorSpaceInput,
  type Landmark,
  type LandmarkInput,
  type PlaceType,
} from "@/lib/geocampus-api";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GeoCampusMap, type GeoPoint } from "./geo-campus-map";
import { PlaceMediaManager } from "./place-media-manager";
import { PlaceQrCode } from "./place-qr-code";

type Entity = "campus" | PlaceType;
type Place = Building | IndoorSpace | Landmark;
type Editor = { kind: Entity; id: string | null } | null;
type DeleteTarget = { kind: Entity; id: string; name: string; campusId?: string } | null;

interface FormState {
  name: string;
  description: string;
  category: string;
  kind: string;
  floor: string;
  building_id: string;
  lat: string;
  lng: string;
  zoom: string;
  active: boolean;
}

const EMPTY_FORM: FormState = {
  name: "", description: "", category: "prédio", kind: "auditório",
  floor: "", building_id: "", lat: "", lng: "", zoom: "17", active: true,
};
const TAB_LABELS: Record<PlaceType, string> = {
  building: "Prédios e blocos", space: "Espaços internos", landmark: "Pontos de referência",
};
const SELECT_CLASS = "min-h-11 w-full min-w-0 rounded-lg border border-input bg-card px-3 py-2 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

function coordinate(value: string, min: number, max: number): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : null;
}

function pointFromForm(form: FormState): GeoPoint | null {
  const lat = coordinate(form.lat, -90, 90);
  const lng = coordinate(form.lng, -180, 180);
  return lat === null || lng === null ? null : { lat, lng };
}

function optionalText(value: string): string | null {
  return value.trim() || null;
}

function fetchMapData(campusId: string) {
  return Promise.all([
    geoCampusApi.buildings.list(campusId),
    geoCampusApi.spaces.list(campusId),
    geoCampusApi.landmarks.list(campusId),
  ]);
}

function formFor(item: Campus | Place, kind: Entity): FormState {
  const base = { ...EMPTY_FORM, name: item.name, description: item.description || "", active: item.active };
  switch (kind) {
    case "campus": {
      const campus = item as Campus;
      return { ...base, lat: String(campus.center_lat), lng: String(campus.center_lng), zoom: String(campus.zoom) };
    }
    case "building": {
      const building = item as Building;
      return { ...base, category: building.category, lat: String(building.entrance_lat), lng: String(building.entrance_lng) };
    }
    case "space": {
      const space = item as IndoorSpace;
      return { ...base, kind: space.kind, floor: space.floor || "", building_id: space.building_id };
    }
    case "landmark": {
      const landmark = item as Landmark;
      return { ...base, lat: String(landmark.lat), lng: String(landmark.lng) };
    }
  }
}

export function GeoCampusManager() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [selectedCampusId, setSelectedCampusId] = useState("");
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [spaces, setSpaces] = useState<IndoorSpace[]>([]);
  const [landmarks, setLandmarks] = useState<Landmark[]>([]);
  const [publicSlug, setPublicSlug] = useState("");
  const [loadingCampuses, setLoadingCampuses] = useState(true);
  const [loadingMap, setLoadingMap] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<PlaceType>("building");
  const [editor, setEditor] = useState<Editor>(null);
  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<DeleteTarget>(null);
  const [focusPoint, setFocusPoint] = useState<GeoPoint | null>(null);
  const [mediaTarget, setMediaTarget] = useState<{ kind: PlaceType; id: string } | null>(null);
  const mapRequest = useRef(0);
  const activeCampusId = useRef("");
  const campusSelect = useRef<HTMLSelectElement>(null);
  const editorHeading = useRef<HTMLHeadingElement>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);
  const previousEditor = useRef<Editor>(null);
  const deleteTrigger = useRef<HTMLElement | null>(null);
  const mediaHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (editor) editorHeading.current?.focus();
    else if (previousEditor.current) editorTrigger.current?.focus();
    previousEditor.current = editor;
  }, [editor]);

  useEffect(() => {
    if (mediaTarget) mediaHeading.current?.focus();
  }, [mediaTarget]);

  const campus = campuses.find((item) => item.id === selectedCampusId) || null;
  const buildingNames = useMemo(() => new Map(buildings.map((item) => [item.id, item.name])), [buildings]);
  const mediaPlaces = mediaTarget?.kind === "building" ? buildings : mediaTarget?.kind === "space" ? spaces : landmarks;
  const mediaPlace = mediaTarget ? mediaPlaces.find((item) => item.id === mediaTarget.id) : null;

  const loadCampuses = useCallback(async () => {
    try {
      const list = await geoCampusApi.campuses.list();
      setCampuses(list);
      setSelectedCampusId((current) => list.some((item) => item.id === current) ? current : list[0]?.id || "");
    } catch {
      setError("Não foi possível carregar os campi. Tente novamente.");
    } finally {
      setLoadingCampuses(false);
    }
  }, []);

  const loadMap = useCallback(async (campusId: string) => {
    if (campusId !== activeCampusId.current) return;
    const requestId = ++mapRequest.current;
    try {
      const [nextBuildings, nextSpaces, nextLandmarks] = await fetchMapData(campusId);
      if (requestId !== mapRequest.current || campusId !== activeCampusId.current) return;
      setBuildings(nextBuildings);
      setSpaces(nextSpaces);
      setLandmarks(nextLandmarks);
    } catch {
      if (requestId === mapRequest.current) setError("Não foi possível carregar o mapa deste campus. Tente novamente.");
    } finally {
      if (requestId === mapRequest.current) setLoadingMap(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void geoCampusApi.campuses.list()
      .then((list) => {
        if (cancelled) return;
        setCampuses(list);
        setSelectedCampusId(list[0]?.id || "");
        setLoadingMap(Boolean(list[0]));
      })
      .catch(() => { if (!cancelled) setError("Não foi possível carregar os campi. Tente novamente."); })
      .finally(() => { if (!cancelled) setLoadingCampuses(false); });
    void configApi.get()
      .then((config) => { if (!cancelled) setPublicSlug(config.public_slug || ""); })
      .catch(() => { /* Campus editing remains available while portal settings cannot be loaded. */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    activeCampusId.current = selectedCampusId;
    if (!selectedCampusId) {
      mapRequest.current += 1;
      return;
    }
    const requestId = ++mapRequest.current;
    void fetchMapData(selectedCampusId)
      .then(([nextBuildings, nextSpaces, nextLandmarks]) => {
        if (requestId !== mapRequest.current) return;
        setBuildings(nextBuildings);
        setSpaces(nextSpaces);
        setLandmarks(nextLandmarks);
      })
      .catch(() => {
        if (requestId === mapRequest.current) setError("Não foi possível carregar o mapa deste campus. Tente novamente.");
      })
      .finally(() => { if (requestId === mapRequest.current) setLoadingMap(false); });
    return () => { mapRequest.current += 1; };
  }, [selectedCampusId]);

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const startCreate = (kind: Entity) => {
    if (kind !== "campus" && !campus) return;
    editorTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setForm({ ...EMPTY_FORM, building_id: kind === "space" ? buildings[0]?.id || "" : "" });
    setFocusPoint(null);
    setEditor({ kind, id: null });
  };

  const startEdit = (kind: Entity, item: Campus | Place) => {
    editorTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setForm(formFor(item, kind));
    setFocusPoint(null);
    setEditor({ kind, id: item.id });
  };

  const selectCampus = (id: string) => {
    activeCampusId.current = id;
    mapRequest.current += 1;
    setSelectedCampusId(id);
    setBuildings([]);
    setSpaces([]);
    setLandmarks([]);
    setLoadingMap(Boolean(id));
    setError("");
    setEditor(null);
    setMediaTarget(null);
    setFocusPoint(null);
  };

  const handlePickPoint = (point: GeoPoint) => {
    setForm((current) => ({ ...current, lat: point.lat.toFixed(7), lng: point.lng.toFixed(7) }));
  };

  const save = async () => {
    if (!editor || saving) return;
    const point = pointFromForm(form);
    const name = form.name.trim();
    if (name.length < 2) {
      toast.error("Informe um nome com pelo menos dois caracteres.");
      return;
    }
    if (editor.kind !== "space" && !point) {
      toast.error("Marque um ponto válido no mapa ou informe latitude e longitude.");
      return;
    }
    if (editor.kind === "campus" && (coordinate(form.zoom, 1, 19) === null || !Number.isInteger(Number(form.zoom)))) {
      toast.error("Informe um zoom de 1 a 19.");
      return;
    }
    if (editor.kind === "space" && (!form.building_id || !form.kind.trim())) {
      toast.error("Selecione o prédio e informe o tipo de espaço.");
      return;
    }

    setSaving(true);
    try {
      if (editor.kind === "campus" && point) {
        const payload: CampusInput = { name, description: optionalText(form.description), center_lat: point.lat, center_lng: point.lng, zoom: Number(form.zoom), active: form.active };
        const saved = editor.id
          ? await geoCampusApi.campuses.update(editor.id, payload)
          : await geoCampusApi.campuses.create(payload);
        setCampuses((current) => [...current.filter((item) => item.id !== saved.id), saved].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
        if (saved.id !== selectedCampusId) {
          setBuildings([]);
          setSpaces([]);
          setLandmarks([]);
          setLoadingMap(true);
          setMediaTarget(null);
        }
        setSelectedCampusId(saved.id);
      } else if (editor.kind === "building" && campus && point) {
        const payload: BuildingInput = { name, description: optionalText(form.description), category: form.category.trim() || "prédio", entrance_lat: point.lat, entrance_lng: point.lng, active: form.active };
        if (editor.id) await geoCampusApi.buildings.update(campus.id, editor.id, payload);
        else await geoCampusApi.buildings.create(campus.id, payload);
        await loadMap(campus.id);
      } else if (editor.kind === "space" && campus) {
        const payload: IndoorSpaceInput = { building_id: form.building_id, name, kind: form.kind.trim(), floor: optionalText(form.floor), description: optionalText(form.description), active: form.active };
        if (editor.id) await geoCampusApi.spaces.update(campus.id, editor.id, payload);
        else await geoCampusApi.spaces.create(campus.id, payload);
        await loadMap(campus.id);
      } else if (editor.kind === "landmark" && campus && point) {
        const payload: LandmarkInput = { name, description: optionalText(form.description), lat: point.lat, lng: point.lng, active: form.active };
        if (editor.id) await geoCampusApi.landmarks.update(campus.id, editor.id, payload);
        else await geoCampusApi.landmarks.create(campus.id, payload);
        await loadMap(campus.id);
      }
      toast.success(editor.id ? "Cadastro atualizado." : "Cadastro criado.");
      setEditor(null);
      setFocusPoint(null);
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "Não foi possível salvar.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      if (deleting.kind === "campus") {
        await geoCampusApi.campuses.delete(deleting.id);
        const remaining = campuses.filter((item) => item.id !== deleting.id);
        setCampuses(remaining);
        selectCampus(remaining[0]?.id || "");
      } else if (deleting.campusId) {
        const resource = deleting.kind === "building" ? geoCampusApi.buildings : deleting.kind === "space" ? geoCampusApi.spaces : geoCampusApi.landmarks;
        await resource.delete(deleting.campusId, deleting.id);
        if (campus?.id === deleting.campusId) await loadMap(deleting.campusId);
      }
      setEditor(null);
      setMediaTarget(null);
      setDeleting(null);
      toast.success("Cadastro excluído.");
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "Não foi possível excluir.");
    }
  };

  const isPointEditor = Boolean(editor && editor.kind !== "space");
  const draftPoint = isPointEditor ? pointFromForm(form) : null;
  const mapCenter = campus ? { lat: campus.center_lat, lng: campus.center_lng } : { lat: 0, lng: 0 };
  const list: Place[] = tab === "building" ? buildings : tab === "space" ? spaces : landmarks;

  return (
    <section className="min-w-0 space-y-6 [&_button]:scroll-mt-24 [&_input]:scroll-mt-24 [&_select]:scroll-mt-24 [&_textarea]:scroll-mt-24" aria-label="Guia visual dos campi">
      <Card>
        <CardContent className="flex min-w-0 flex-col gap-4 p-4 sm:flex-row sm:flex-wrap sm:items-end md:p-6">
          <div className="min-w-0 flex-1 space-y-2 sm:basis-64">
            <Label htmlFor="campus-select">Campus</Label>
            <select id="campus-select" ref={campusSelect} className={SELECT_CLASS} value={selectedCampusId} onChange={(event) => selectCampus(event.target.value)} disabled={loadingCampuses || saving || Boolean(deleting)}>
              {!campuses.length && <option value="">Nenhum campus cadastrado</option>}
              {campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <Button onClick={() => startCreate("campus")} disabled={saving || Boolean(deleting)}><Plus aria-hidden="true" className="h-4 w-4" /> Novo campus</Button>
          {campus && <>
            <Button variant="outline" onClick={() => startEdit("campus", campus)} disabled={saving || Boolean(deleting)}><Pencil aria-hidden="true" className="h-4 w-4" /> Editar campus</Button>
            <Button variant="outline" size="icon" className="text-destructive" aria-label={"Excluir campus " + campus.name} onClick={(event) => { deleteTrigger.current = event.currentTarget; setDeleting({ kind: "campus", id: campus.id, name: campus.name }); }} disabled={saving}><Trash2 aria-hidden="true" className="h-4 w-4" /></Button>
          </>}
        </CardContent>
      </Card>
      {loadingCampuses && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />Carregando campi...</p>}
      {error && <Card className="border-destructive/40"><CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between"><p role="alert" className="text-sm text-foreground">{error}</p><Button variant="outline" onClick={() => { setError(""); setLoadingCampuses(true); void loadCampuses(); if (campus) { setLoadingMap(true); void loadMap(campus.id); } }}>Tentar novamente</Button></CardContent></Card>}

      <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,1fr)]">
        <Card className="min-w-0 overflow-hidden">
          <CardHeader className="pb-3">
            <CardTitle className="flex min-w-0 items-start gap-2 text-lg"><MapPin aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" /><h2 className="min-w-0 [overflow-wrap:anywhere]">{campus?.name || "Mapa mundial"}</h2></CardTitle>
            <p id="geo-map-instructions" className="text-sm text-muted-foreground">{isPointEditor ? "Clique no mapa ou arraste o ponto em edição. Você também pode informar latitude e longitude no formulário." : "Consulte os blocos e os pontos de referência cadastrados no campus."}</p>
          </CardHeader>
          <CardContent className="space-y-3 pb-4">
            <GeoCampusMap key={selectedCampusId || "new-campus"} center={mapCenter} zoom={campus?.zoom || 2} buildings={buildings} landmarks={landmarks} draftPoint={draftPoint} focusPoint={focusPoint} onPickPoint={isPointEditor ? handlePickPoint : undefined} />
            <ul aria-label="Legenda do mapa" className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
              <li className="flex items-center gap-2"><span aria-hidden="true" className="size-3 rounded-full bg-chart-4" />Prédios e blocos</li>
              <li className="flex items-center gap-2"><span aria-hidden="true" className="size-3 rounded-full bg-primary" />Pontos de referência</li>
              {isPointEditor && <li className="flex items-center gap-2"><span aria-hidden="true" className="size-3 rounded-full bg-destructive" />Ponto em edição</li>}
            </ul>
            <p role="status" className="text-xs text-muted-foreground">{loadingMap ? "Atualizando mapa..." : buildings.length + " prédio(s), " + landmarks.length + " ponto(s) de referência"}</p>
          </CardContent>
        </Card>

        {editor ? (
          <Card className="min-w-0" role="region" aria-labelledby="geo-editor-title">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg"><h2 id="geo-editor-title" ref={editorHeading} tabIndex={-1} className="scroll-mt-24 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{editor.id ? "Editar" : "Cadastrar"} {editor.kind === "campus" ? "campus" : editor.kind === "building" ? "prédio" : editor.kind === "space" ? "espaço interno" : "ponto de referência"}</h2></CardTitle>
              <p className="text-sm text-muted-foreground">{editor.kind === "campus" ? "Centro e configurações do campus." : "Campus: " + campus?.name}</p>
            </CardHeader>
            <CardContent className="min-w-0 space-y-5 [&>div]:min-w-0">
              <div className="space-y-1.5"><Label htmlFor="geo-name">Nome</Label><Input id="geo-name" maxLength={200} aria-required="true" value={form.name} onChange={(event) => updateForm("name", event.target.value)} /></div>
              <div className="space-y-1.5"><Label htmlFor="geo-description">Descrição (opcional)</Label><Textarea id="geo-description" maxLength={2000} className="field-sizing-fixed min-h-24 max-h-48 resize-none overflow-y-auto" rows={3} value={form.description} onChange={(event) => updateForm("description", event.target.value)} /></div>
              {editor.kind === "building" && <div className="space-y-1.5"><Label htmlFor="geo-category">Categoria</Label><Input id="geo-category" maxLength={100} value={form.category} onChange={(event) => updateForm("category", event.target.value)} placeholder="Bloco, biblioteca, restaurante..." /></div>}
              {editor.kind === "space" && <>
                <div className="space-y-1.5"><Label htmlFor="geo-building">Prédio ou bloco</Label><select id="geo-building" className={SELECT_CLASS} value={form.building_id} onChange={(event) => updateForm("building_id", event.target.value)}><option value="">Selecione</option>{buildings.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
                <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 [&>div]:min-w-0">
                  <div className="space-y-1.5"><Label htmlFor="geo-kind">Tipo de espaço</Label><Input id="geo-kind" maxLength={100} value={form.kind} onChange={(event) => updateForm("kind", event.target.value)} list="space-kinds" /><datalist id="space-kinds"><option value="sala" /><option value="laboratório" /><option value="auditório" /></datalist></div>
                  <div className="space-y-1.5"><Label htmlFor="geo-floor">Piso</Label><Input id="geo-floor" maxLength={50} value={form.floor} onChange={(event) => updateForm("floor", event.target.value)} placeholder="Térreo, 2º..." /></div>
                </div>
              </>}
              {isPointEditor && <>
                <p className="text-sm text-muted-foreground">{editor.kind === "campus" ? "Marque o centro aproximado do campus." : "Marque o local que o visitante poderá reconhecer pelas fotos."}</p>
                <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 [&>div]:min-w-0">
                  <div className="space-y-1.5"><Label htmlFor="geo-lat">Latitude</Label><Input id="geo-lat" type="number" step="any" min="-90" max="90" value={form.lat} onChange={(event) => updateForm("lat", event.target.value)} /></div>
                  <div className="space-y-1.5"><Label htmlFor="geo-lng">Longitude</Label><Input id="geo-lng" type="number" step="any" min="-180" max="180" value={form.lng} onChange={(event) => updateForm("lng", event.target.value)} /></div>
                </div>
                {draftPoint && <Button type="button" size="sm" variant="outline" onClick={() => setFocusPoint({ ...draftPoint })}>Ir para este ponto no mapa</Button>}
              </>}
              {editor.kind === "campus" && <div className="space-y-1.5"><Label htmlFor="geo-zoom">Zoom inicial do mapa (1 a 19)</Label><Input id="geo-zoom" type="number" min="1" max="19" value={form.zoom} onChange={(event) => updateForm("zoom", event.target.value)} /></div>}
              <label className="flex min-h-11 items-center gap-3 rounded-lg border border-border bg-muted/40 p-3 text-sm"><input className="size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" type="checkbox" checked={form.active} onChange={(event) => updateForm("active", event.target.checked)} />Ativo para visitantes</label>
              <div className="flex flex-col gap-2 pt-2 sm:flex-row">
                <Button onClick={() => void save()} disabled={saving} aria-busy={saving}>{saving && <Loader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />}{saving ? "Salvando..." : "Salvar"}</Button>
                <Button variant="outline" onClick={() => setEditor(null)} disabled={saving}>Cancelar</Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card><CardHeader><CardTitle className="text-lg">Como preparar o guia visual</CardTitle></CardHeader><CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>1. Cadastre o campus e ajuste o mapa na área da instituição.</p>
            <p>2. Marque os blocos e os pontos de referência e cadastre os espaços internos de cada bloco.</p>
            <p>3. Abra Fotos e QR Code em um local para adicionar imagens da fachada, entrada e outras referências.</p>
            <p>4. Imprima o QR Code do local e afixe-o no campus para abrir a mesma ficha disponível pelo mapa.</p>
            {!campus && <Button onClick={() => startCreate("campus")}><Plus aria-hidden="true" className="h-4 w-4" /> Cadastrar primeiro campus</Button>}
          </CardContent></Card>
        )}
      </div>

      {campus && <Card className="min-w-0">
        <CardHeader className="min-w-0 gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0"><CardTitle className="text-lg [overflow-wrap:anywhere]"><h2>Dados de {campus.name}</h2></CardTitle><p className="mt-1 text-sm text-muted-foreground">Organize os blocos, seus espaços internos e as referências visuais.</p></div>
          <Button className="shrink-0" onClick={() => startCreate(tab)} disabled={saving || loadingMap || (tab === "space" && !buildings.length)}><Plus aria-hidden="true" className="h-4 w-4" />{tab === "building" ? "Novo prédio" : tab === "space" ? "Novo espaço" : "Novo ponto de referência"}</Button>
        </CardHeader>
        <CardContent className="min-w-0">
          <Tabs value={tab} onValueChange={(value) => setTab(value as PlaceType)} className="min-w-0 gap-4">
            <TabsList aria-label="Dados do campus" className="grid w-full grid-cols-1 gap-2 rounded-none bg-transparent p-0 group-data-[orientation=horizontal]/tabs:h-auto sm:grid-cols-3">
              {(Object.keys(TAB_LABELS) as PlaceType[]).map((key) => <TabsTrigger key={key} value={key} className="min-h-11 whitespace-normal rounded-lg border border-border bg-card px-3 py-2 text-foreground data-[state=active]:border-primary data-[state=active]:bg-primary/10 data-[state=active]:text-primary">{TAB_LABELS[key]}</TabsTrigger>)}
            </TabsList>
            <TabsContent value={tab} className="min-w-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              {loadingMap ? <p role="status" className="flex items-center gap-2 rounded-lg border border-dashed p-6 text-sm text-muted-foreground"><Loader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />Carregando dados do campus...</p> : !list.length ? <p role="status" className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{tab === "space" && !buildings.length ? "Cadastre um prédio antes de adicionar espaços internos." : "Nenhum item em " + TAB_LABELS[tab].toLowerCase() + "."}</p> : (
                <div className="grid min-w-0 gap-4 xl:grid-cols-2">
                  {list.map((item) => {
                    let subtitle: string;
                    if (tab === "building") subtitle = (item as Building).category;
                    else if (tab === "space") {
                      const space = item as IndoorSpace;
                      subtitle = space.kind + " · " + (buildingNames.get(space.building_id) || "Bloco indisponível") + (space.floor ? " · " + space.floor : "");
                    } else subtitle = "Ponto de referência";
                    return (
                      <article key={item.id} aria-labelledby={"geo-item-" + item.id} className="flex min-w-0 flex-col gap-4 rounded-lg border border-border bg-card p-4">
                        <div className="flex min-w-0 items-start gap-3">
                          <div aria-hidden="true" className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary">{tab === "building" ? <Building2 className="h-4 w-4" /> : <MapPin className="h-4 w-4" />}</div>
                          <div className="min-w-0 flex-1"><h3 id={"geo-item-" + item.id} className="font-medium [overflow-wrap:anywhere]">{item.name}</h3>{!item.active && <Badge variant="secondary" className="mt-2">Inativo</Badge>}<p className="mt-2 text-sm text-muted-foreground [overflow-wrap:anywhere]">{subtitle}</p><p className="mt-1 text-xs text-muted-foreground">{item.photos?.length || 0} foto(s)</p></div>
                        </div>
                        <div className="mt-auto flex flex-wrap justify-end gap-2">
                          <Button variant="outline" aria-label={"Fotos e QR Code de " + item.name} onClick={() => setMediaTarget({ kind: tab, id: item.id })}><Camera aria-hidden="true" className="h-4 w-4" />Fotos e QR Code</Button>
                          <Button variant="outline" size="icon" aria-label={"Editar " + item.name} onClick={() => startEdit(tab, item)} disabled={saving}><Pencil aria-hidden="true" className="h-4 w-4" /></Button>
                          <Button variant="outline" size="icon" className="text-destructive" aria-label={"Excluir " + item.name} onClick={(event) => { deleteTrigger.current = event.currentTarget; setDeleting({ kind: tab, id: item.id, name: item.name, campusId: campus.id }); }} disabled={saving}><Trash2 aria-hidden="true" className="h-4 w-4" /></Button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>}

      {campus && mediaTarget && mediaPlace && (
        <Card role="region" aria-labelledby="place-media-title">
          <CardHeader><CardTitle><h2 id="place-media-title" tabIndex={-1} ref={mediaHeading} className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [overflow-wrap:anywhere]">Fotos e QR Code de {mediaPlace.name}</h2></CardTitle></CardHeader>
          <CardContent className="grid min-w-0 gap-6 lg:grid-cols-2">
            <PlaceMediaManager key={mediaTarget.kind + mediaPlace.id} campusId={campus.id} placeType={mediaTarget.kind} placeId={mediaPlace.id} placeName={mediaPlace.name} photos={mediaPlace.photos || []} onChanged={() => loadMap(campus.id)} />
            <PlaceQrCode key={mediaPlace.public_code} publicSlug={publicSlug} placeType={mediaTarget.kind} publicCode={mediaPlace.public_code} placeName={mediaPlace.name} />
          </CardContent>
        </Card>
      )}

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open) setDeleting(null); }}>
        <AlertDialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto" onCloseAutoFocus={(event) => { event.preventDefault(); (deleteTrigger.current?.isConnected ? deleteTrigger.current : campusSelect.current)?.focus(); }}>
          <AlertDialogHeader className="text-left"><AlertDialogTitle className="max-h-[35dvh] overflow-y-auto [overflow-wrap:anywhere]" tabIndex={0}>Excluir {deleting?.name}?</AlertDialogTitle><AlertDialogDescription>A exclusão remove o cadastro e suas fotos. Ao excluir um prédio, seus espaços internos também serão removidos.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter className="flex-col gap-2 sm:flex-row"><AlertDialogCancel>Cancelar</AlertDialogCancel><AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={() => void remove()}>Excluir</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Building2, MapPin, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
  geoCampusApi,
  type Building,
  type BuildingInput,
  type Campus,
  type CampusInput,
  type IndoorSpace,
  type IndoorSpaceInput,
  type PathEdge,
  type PathEdgeInput,
  type PathNode,
  type PathNodeInput,
} from "@/lib/geocampus-api";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { GeoCampusMap, type GeoPoint } from "./geo-campus-map";

type Entity = "campus" | "building" | "space" | "node" | "edge";
type Tab = Exclude<Entity, "campus">;
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
  entrance_node_id: string;
  from_node_id: string;
  to_node_id: string;
  distance_m: string;
  active: boolean;
  accessible: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  category: "prédio",
  kind: "auditório",
  floor: "",
  building_id: "",
  lat: "",
  lng: "",
  zoom: "17",
  entrance_node_id: "",
  from_node_id: "",
  to_node_id: "",
  distance_m: "",
  active: true,
  accessible: true,
};

const TAB_LABELS: Record<Tab, string> = {
  building: "Prédios",
  space: "Espaços internos",
  node: "Pontos do caminho",
  edge: "Trechos",
};

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

function formatCoordinate(value: number): string {
  return value.toFixed(6);
}

function fetchMapData(campusId: string) {
  return Promise.all([
    geoCampusApi.buildings.list(campusId),
    geoCampusApi.spaces.list(campusId),
    geoCampusApi.nodes.list(campusId),
    geoCampusApi.edges.list(campusId),
  ]);
}

function formFor(item: Campus | Building | IndoorSpace | PathNode | PathEdge, kind: Entity): FormState {
  const base = { ...EMPTY_FORM };
  switch (kind) {
    case "campus": {
      const campus = item as Campus;
      return { ...base, name: campus.name, description: campus.description || "", lat: String(campus.center_lat), lng: String(campus.center_lng), zoom: String(campus.zoom), active: campus.active };
    }
    case "building": {
      const building = item as Building;
      return { ...base, name: building.name, description: building.description || "", category: building.category, lat: String(building.entrance_lat), lng: String(building.entrance_lng), entrance_node_id: building.entrance_node_id || "", active: building.active };
    }
    case "space": {
      const space = item as IndoorSpace;
      return { ...base, name: space.name, description: space.description || "", kind: space.kind, floor: space.floor || "", building_id: space.building_id, active: space.active };
    }
    case "node": {
      const node = item as PathNode;
      return { ...base, name: node.label || "", lat: String(node.lat), lng: String(node.lng) };
    }
    case "edge": {
      const edge = item as PathEdge;
      return { ...base, from_node_id: edge.from_node_id, to_node_id: edge.to_node_id, distance_m: edge.distance_m === null ? "" : String(edge.distance_m), accessible: edge.accessible, active: edge.active };
    }
  }
}

export function GeoCampusManager() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [selectedCampusId, setSelectedCampusId] = useState("");
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [spaces, setSpaces] = useState<IndoorSpace[]>([]);
  const [nodes, setNodes] = useState<PathNode[]>([]);
  const [edges, setEdges] = useState<PathEdge[]>([]);
  const [loadingCampuses, setLoadingCampuses] = useState(true);
  const [loadingMap, setLoadingMap] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("building");
  const [editor, setEditor] = useState<Editor>(null);
  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<DeleteTarget>(null);
  const [focusPoint, setFocusPoint] = useState<GeoPoint | null>(null);
  const mapRequest = useRef(0);

  const campus = campuses.find((item) => item.id === selectedCampusId) || null;
  const buildingNames = useMemo(() => new Map(buildings.map((item) => [item.id, item.name])), [buildings]);
  const nodeNames = useMemo(() => new Map(nodes.map((item, index) => [item.id, item.label || `Ponto ${index + 1}`])), [nodes]);

  const loadCampuses = useCallback(async () => {
    try {
      const list = await geoCampusApi.campuses.list();
      setCampuses(list);
      setSelectedCampusId((current) => {
        if (list.some((item) => item.id === current)) return current;
        return list[0]?.id || "";
      });
    } catch {
      setError("Não foi possível carregar os campi. Tente novamente.");
    } finally {
      setLoadingCampuses(false);
    }
  }, []);

  const loadMap = useCallback(async (campusId: string) => {
    const requestId = ++mapRequest.current;
    try {
      const [nextBuildings, nextSpaces, nextNodes, nextEdges] = await fetchMapData(campusId);
      if (requestId !== mapRequest.current) return;
      setBuildings(nextBuildings);
      setSpaces(nextSpaces);
      setNodes(nextNodes);
      setEdges(nextEdges);
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
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedCampusId) {
      mapRequest.current += 1;
      return;
    }
    const requestId = ++mapRequest.current;
    void fetchMapData(selectedCampusId)
      .then(([nextBuildings, nextSpaces, nextNodes, nextEdges]) => {
        if (requestId !== mapRequest.current) return;
        setBuildings(nextBuildings);
        setSpaces(nextSpaces);
        setNodes(nextNodes);
        setEdges(nextEdges);
      })
      .catch(() => {
        if (requestId === mapRequest.current) setError("Não foi possível carregar o mapa deste campus. Tente novamente.");
      })
      .finally(() => {
        if (requestId === mapRequest.current) setLoadingMap(false);
      });
  }, [selectedCampusId]);

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const startCreate = (kind: Entity) => {
    if (kind !== "campus" && !campus) return;
    setForm({
      ...EMPTY_FORM,
      building_id: kind === "space" ? buildings[0]?.id || "" : "",
      from_node_id: kind === "edge" ? nodes[0]?.id || "" : "",
      to_node_id: kind === "edge" ? nodes[1]?.id || "" : "",
    });
    setFocusPoint(null);
    setEditor({ kind, id: null });
  };

  const startEdit = (kind: Entity, item: Campus | Building | IndoorSpace | PathNode | PathEdge) => {
    setForm(formFor(item, kind));
    setFocusPoint(null);
    setEditor({ kind, id: item.id });
  };

  const selectCampus = (id: string) => {
    mapRequest.current += 1;
    setSelectedCampusId(id);
    setBuildings([]);
    setSpaces([]);
    setNodes([]);
    setEdges([]);
    setLoadingMap(Boolean(id));
    setError("");
    setEditor(null);
    setFocusPoint(null);
  };

  const handlePickPoint = (point: GeoPoint) => {
    setForm((current) => ({ ...current, lat: point.lat.toFixed(7), lng: point.lng.toFixed(7) }));
  };

  const locateAdmin = () => {
    if (!navigator.geolocation) {
      toast.error("Este navegador não oferece localização.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const point = { lat: coords.latitude, lng: coords.longitude };
        setFocusPoint(point);
        if (editor?.kind === "campus" || editor?.kind === "building" || editor?.kind === "node") handlePickPoint(point);
      },
      () => toast.error("Não foi possível acessar sua localização."),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const save = async () => {
    if (!editor || saving) return;
    const point = pointFromForm(form);
    const kind = editor.kind;
    const name = form.name.trim();
    if (["campus", "building", "space"].includes(kind) && !name) {
      toast.error("Informe o nome.");
      return;
    }
    if (["campus", "building", "node"].includes(kind) && !point) {
      toast.error("Marque um ponto válido no mapa ou informe latitude e longitude.");
      return;
    }
    if (kind === "campus" && (coordinate(form.zoom, 1, 19) === null || !Number.isInteger(Number(form.zoom)))) {
      toast.error("Informe um zoom de 1 a 19.");
      return;
    }
    if (kind === "space" && (!form.building_id || !form.kind.trim())) {
      toast.error("Selecione o prédio e informe o tipo de espaço.");
      return;
    }
    if (kind === "edge" && (!form.from_node_id || !form.to_node_id || form.from_node_id === form.to_node_id)) {
      toast.error("Selecione dois pontos diferentes para o trecho.");
      return;
    }
    const distance = form.distance_m.trim() ? Number(form.distance_m) : null;
    if (kind === "edge" && distance !== null && (!Number.isFinite(distance) || distance <= 0)) {
      toast.error("A distância deve ser maior que zero.");
      return;
    }

    setSaving(true);
    try {
      if (kind === "campus" && point) {
        const payload: CampusInput = { name, description: optionalText(form.description), center_lat: point.lat, center_lng: point.lng, zoom: Number(form.zoom), active: form.active };
        const saved = editor.id
          ? await geoCampusApi.campuses.update(editor.id, payload)
          : await geoCampusApi.campuses.create(payload);
        setCampuses((current) => [...current.filter((item) => item.id !== saved.id), saved].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
        if (saved.id !== selectedCampusId) {
          setBuildings([]);
          setSpaces([]);
          setNodes([]);
          setEdges([]);
          setLoadingMap(true);
        }
        setSelectedCampusId(saved.id);
      } else if (kind === "building" && campus && point) {
        const payload: BuildingInput = { name, description: optionalText(form.description), category: form.category.trim() || "prédio", entrance_lat: point.lat, entrance_lng: point.lng, entrance_node_id: form.entrance_node_id || null, active: form.active };
        if (editor.id) await geoCampusApi.buildings.update(campus.id, editor.id, payload);
        else await geoCampusApi.buildings.create(campus.id, payload);
        await loadMap(campus.id);
      } else if (kind === "space" && campus) {
        const payload: IndoorSpaceInput = { building_id: form.building_id, name, kind: form.kind.trim(), floor: optionalText(form.floor), description: optionalText(form.description), active: form.active };
        if (editor.id) await geoCampusApi.spaces.update(campus.id, editor.id, payload);
        else await geoCampusApi.spaces.create(campus.id, payload);
        await loadMap(campus.id);
      } else if (kind === "node" && campus && point) {
        const payload: PathNodeInput = { label: optionalText(form.name), lat: point.lat, lng: point.lng };
        if (editor.id) await geoCampusApi.nodes.update(campus.id, editor.id, payload);
        else await geoCampusApi.nodes.create(campus.id, payload);
        await loadMap(campus.id);
      } else if (kind === "edge" && campus) {
        const payload: PathEdgeInput = { from_node_id: form.from_node_id, to_node_id: form.to_node_id, distance_m: distance, accessible: form.accessible, active: form.active };
        if (editor.id) await geoCampusApi.edges.update(campus.id, editor.id, payload);
        else await geoCampusApi.edges.create(campus.id, payload);
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
        setBuildings([]);
        setSpaces([]);
        setNodes([]);
        setEdges([]);
        setLoadingMap(Boolean(remaining[0]));
        setSelectedCampusId(remaining[0]?.id || "");
      } else if (deleting.campusId) {
        if (deleting.kind === "building") await geoCampusApi.buildings.delete(deleting.campusId, deleting.id);
        if (deleting.kind === "space") await geoCampusApi.spaces.delete(deleting.campusId, deleting.id);
        if (deleting.kind === "node") await geoCampusApi.nodes.delete(deleting.campusId, deleting.id);
        if (deleting.kind === "edge") await geoCampusApi.edges.delete(deleting.campusId, deleting.id);
        if (campus?.id === deleting.campusId) await loadMap(deleting.campusId);
      }
      setEditor(null);
      setDeleting(null);
      toast.success("Cadastro excluído.");
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "Não foi possível excluir.");
    }
  };

  const isPointEditor = editor?.kind === "campus" || editor?.kind === "building" || editor?.kind === "node";
  const draftPoint = isPointEditor ? pointFromForm(form) : null;
  const mapCenter = campus ? { lat: campus.center_lat, lng: campus.center_lng } : { lat: 0, lng: 0 };
  const list: Array<Building | IndoorSpace | PathNode | PathEdge> = tab === "building" ? buildings : tab === "space" ? spaces : tab === "node" ? nodes : edges;

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <div className="min-w-52 flex-1 space-y-1.5">
            <Label htmlFor="campus-select">Campus</Label>
            <select id="campus-select" className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm" value={selectedCampusId} onChange={(event) => selectCampus(event.target.value)} disabled={loadingCampuses || saving || Boolean(deleting)}>
              {!campuses.length && <option value="">Nenhum campus cadastrado</option>}
              {campuses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <Button onClick={() => startCreate("campus")} disabled={saving || Boolean(deleting)}><Plus className="h-4 w-4" /> Novo campus</Button>
          {campus && <>
            <Button variant="outline" onClick={() => startEdit("campus", campus)} disabled={saving || Boolean(deleting)}><Pencil className="h-4 w-4" /> Editar campus</Button>
            <Button variant="outline" aria-label={`Excluir campus ${campus.name}`} onClick={() => setDeleting({ kind: "campus", id: campus.id, name: campus.name })} disabled={saving}><Trash2 className="h-4 w-4" /></Button>
          </>}
        </CardContent>
      </Card>

      {error && <Card className="border-destructive/40"><CardContent className="flex flex-wrap items-center justify-between gap-2 p-4"><p role="alert" className="text-sm text-destructive">{error}</p><Button variant="outline" onClick={() => { setError(""); setLoadingCampuses(true); void loadCampuses(); if (campus) { setLoadingMap(true); void loadMap(campus.id); } }}>Tentar novamente</Button></CardContent></Card>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(330px,1fr)]">
        <Card className="overflow-hidden">
          <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-lg"><MapPin className="h-5 w-5" /> {campus?.name || "Mapa mundial"}</CardTitle><p className="text-sm text-muted-foreground">{isPointEditor ? "Clique no mapa para definir o ponto. Você também pode arrastar o marcador vermelho." : "Entradas em roxo, pontos do caminho em azul, trechos acessíveis em verde e trechos com barreira em laranja."}</p></CardHeader>
          <CardContent className="space-y-3 pb-4">
            <GeoCampusMap key={selectedCampusId || "new-campus"} center={mapCenter} zoom={campus?.zoom || 2} buildings={buildings} nodes={nodes} edges={edges} draftPoint={draftPoint} focusPoint={focusPoint} onPickPoint={isPointEditor ? handlePickPoint : undefined} />
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>{loadingMap ? "Atualizando mapa..." : `${buildings.length} prédio(s), ${nodes.length} ponto(s), ${edges.length} trecho(s)`}</span>
              <Button type="button" variant="outline" size="sm" onClick={locateAdmin}>{isPointEditor ? "Marcar minha localização" : "Ir para minha localização"}</Button>
            </div>
          </CardContent>
        </Card>

        {editor ? (
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-lg">{editor.id ? "Editar" : "Cadastrar"} {editor.kind === "campus" ? "campus" : editor.kind === "building" ? "prédio" : editor.kind === "space" ? "espaço interno" : editor.kind === "node" ? "ponto do caminho" : "trecho"}</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {(editor.kind === "campus" || editor.kind === "building" || editor.kind === "space") && <div className="space-y-1.5"><Label htmlFor="geo-name">Nome</Label><Input id="geo-name" value={form.name} onChange={(event) => updateForm("name", event.target.value)} placeholder={editor.kind === "campus" ? "Campus Central" : editor.kind === "building" ? "Bloco A" : "Auditório Principal"} /></div>}
              {editor.kind === "node" && <div className="space-y-1.5"><Label htmlFor="geo-name">Identificação do ponto (opcional)</Label><Input id="geo-name" value={form.name} onChange={(event) => updateForm("name", event.target.value)} placeholder="Portão norte" /></div>}
              {(editor.kind === "campus" || editor.kind === "building" || editor.kind === "space") && <div className="space-y-1.5"><Label htmlFor="geo-description">Descrição (opcional)</Label><Textarea id="geo-description" rows={2} value={form.description} onChange={(event) => updateForm("description", event.target.value)} /></div>}
              {editor.kind === "building" && <div className="space-y-1.5"><Label htmlFor="geo-category">Categoria</Label><Input id="geo-category" value={form.category} onChange={(event) => updateForm("category", event.target.value)} placeholder="Bloco, biblioteca, restaurante..." /></div>}
              {editor.kind === "space" && <>
                <div className="space-y-1.5"><Label htmlFor="geo-building">Prédio</Label><select id="geo-building" className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm" value={form.building_id} onChange={(event) => updateForm("building_id", event.target.value)}><option value="">Selecione</option>{buildings.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
                <div className="grid grid-cols-2 gap-3"><div className="space-y-1.5"><Label htmlFor="geo-kind">Tipo de espaço</Label><Input id="geo-kind" value={form.kind} onChange={(event) => updateForm("kind", event.target.value)} placeholder="Auditório, laboratório..." /></div><div className="space-y-1.5"><Label htmlFor="geo-floor">Piso</Label><Input id="geo-floor" value={form.floor} onChange={(event) => updateForm("floor", event.target.value)} placeholder="Térreo, 2º..." /></div></div>
              </>}
              {isPointEditor && <>
                <p className="text-sm text-muted-foreground">{editor.kind === "building" ? "Marque a entrada usada pelos visitantes, não o centro do prédio." : editor.kind === "node" ? "Marque um cruzamento ou mudança de direção do caminho." : "Marque o centro aproximado do campus. Pode ajustar as coordenadas manualmente."}</p>
                <div className="grid grid-cols-2 gap-3"><div className="space-y-1.5"><Label htmlFor="geo-lat">Latitude</Label><Input id="geo-lat" type="number" step="any" min="-90" max="90" value={form.lat} onChange={(event) => updateForm("lat", event.target.value)} /></div><div className="space-y-1.5"><Label htmlFor="geo-lng">Longitude</Label><Input id="geo-lng" type="number" step="any" min="-180" max="180" value={form.lng} onChange={(event) => updateForm("lng", event.target.value)} /></div></div>
                {draftPoint && <Button type="button" size="sm" variant="outline" onClick={() => setFocusPoint({ ...draftPoint })}>Ir para este ponto no mapa</Button>}
              </>}
              {editor.kind === "campus" && <div className="space-y-1.5"><Label htmlFor="geo-zoom">Zoom inicial do mapa (1 a 19)</Label><Input id="geo-zoom" type="number" min="1" max="19" value={form.zoom} onChange={(event) => updateForm("zoom", event.target.value)} /></div>}
              {editor.kind === "building" && <div className="space-y-1.5"><Label htmlFor="geo-entrance-node">Ponto do caminho na entrada</Label><select id="geo-entrance-node" className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm" value={form.entrance_node_id} onChange={(event) => updateForm("entrance_node_id", event.target.value)}><option value="">Sem ligação com a rota</option>{nodes.map((item, index) => <option key={item.id} value={item.id}>{item.label || `Ponto ${index + 1}`} ({formatCoordinate(item.lat)}, {formatCoordinate(item.lng)})</option>)}</select><p className="text-xs text-muted-foreground">Para traçar uma rota até esta entrada, crie um ponto do caminho próximo dela e selecione-o aqui.</p></div>}
              {editor.kind === "edge" && <>
                <div className="space-y-1.5"><Label htmlFor="geo-from">Ponto inicial</Label><select id="geo-from" className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm" value={form.from_node_id} onChange={(event) => updateForm("from_node_id", event.target.value)}><option value="">Selecione</option>{nodes.map((item, index) => <option key={item.id} value={item.id}>{item.label || `Ponto ${index + 1}`}</option>)}</select></div>
                <div className="space-y-1.5"><Label htmlFor="geo-to">Ponto final</Label><select id="geo-to" className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm" value={form.to_node_id} onChange={(event) => updateForm("to_node_id", event.target.value)}><option value="">Selecione</option>{nodes.map((item, index) => <option key={item.id} value={item.id}>{item.label || `Ponto ${index + 1}`}</option>)}</select></div>
                <div className="space-y-1.5"><Label htmlFor="geo-distance">Comprimento real em metros (opcional)</Label><Input id="geo-distance" type="number" min="0" step="any" value={form.distance_m} onChange={(event) => updateForm("distance_m", event.target.value)} placeholder="Calculado pelas coordenadas" /><p className="text-xs text-muted-foreground">Use um valor medido se o trecho não for reto.</p></div>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.accessible} onChange={(event) => updateForm("accessible", event.target.checked)} />Trecho acessível (sem escadas ou barreiras)</label>
              </>}
              {(editor.kind === "campus" || editor.kind === "building" || editor.kind === "space" || editor.kind === "edge") && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} onChange={(event) => updateForm("active", event.target.checked)} />Ativo para visitantes</label>}
              <div className="flex flex-wrap gap-2 pt-2"><Button onClick={() => void save()} disabled={saving}>{saving ? "Salvando..." : "Salvar"}</Button><Button variant="outline" onClick={() => setEditor(null)} disabled={saving}>Cancelar</Button></div>
            </CardContent>
          </Card>
        ) : <Card><CardHeader><CardTitle className="text-lg">Como preparar a navegação</CardTitle></CardHeader><CardContent className="space-y-3 text-sm text-muted-foreground"><p>1. Cadastre o campus e ajuste o mapa na área da instituição.</p><p>2. Marque a entrada de cada prédio e descreva seus auditórios, laboratórios e outros espaços.</p><p>3. Marque cruzamentos e mudanças de direção. Ligue pontos vizinhos por trechos e indique se cada um é acessível.</p><p>4. Edite os prédios para ligar suas entradas aos pontos da rede. A rota termina na entrada vinculada.</p>{!campus && <Button onClick={() => startCreate("campus")}><Plus className="h-4 w-4" /> Cadastrar primeiro campus</Button>}</CardContent></Card>}
      </div>

      {campus && <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle className="text-lg">Dados de {campus.name}</CardTitle><p className="mt-1 text-sm text-muted-foreground">Organize os locais e o grafo que será usado pelas rotas.</p></div><Button onClick={() => startCreate(tab)} disabled={(tab === "space" && !buildings.length) || (tab === "edge" && nodes.length < 2)}><Plus className="h-4 w-4" /> {tab === "building" ? "Novo prédio" : tab === "space" ? "Novo espaço" : tab === "node" ? "Novo ponto" : "Novo trecho"}</Button></CardHeader>
        <CardContent className="space-y-4"><div className="flex flex-wrap gap-2" role="tablist" aria-label="Dados do campus">{(Object.keys(TAB_LABELS) as Tab[]).map((key) => <Button key={key} role="tab" aria-selected={tab === key} variant={tab === key ? "default" : "outline"} size="sm" onClick={() => setTab(key)}>{TAB_LABELS[key]}</Button>)}</div>
          {!list.length ? <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{tab === "space" && !buildings.length ? "Cadastre um prédio antes de adicionar espaços internos." : tab === "edge" && nodes.length < 2 ? "Cadastre pelo menos dois pontos antes de conectá-los." : `Nenhum item em ${TAB_LABELS[tab].toLowerCase()}.`}</p> : <div className="grid gap-3 md:grid-cols-2">{list.map((item, index) => {
            const title = tab === "building" ? (item as Building).name : tab === "space" ? (item as IndoorSpace).name : tab === "node" ? (item as PathNode).label || `Ponto ${index + 1}` : `${nodeNames.get((item as PathEdge).from_node_id) || "Ponto"} → ${nodeNames.get((item as PathEdge).to_node_id) || "Ponto"}`;
            const subtitle = tab === "building" ? `${(item as Building).category} · entrada ${formatCoordinate((item as Building).entrance_lat)}, ${formatCoordinate((item as Building).entrance_lng)}` : tab === "space" ? `${(item as IndoorSpace).kind} · ${buildingNames.get((item as IndoorSpace).building_id) || "Prédio removido"}${(item as IndoorSpace).floor ? ` · ${(item as IndoorSpace).floor}` : ""}` : tab === "node" ? `${formatCoordinate((item as PathNode).lat)}, ${formatCoordinate((item as PathNode).lng)}` : `${(item as PathEdge).accessible ? "Acessível" : "Com barreira"}${(item as PathEdge).distance_m ? ` · ${(item as PathEdge).distance_m} m` : ""}`;
            return <div key={item.id} className="flex items-start gap-3 rounded-lg border p-3"><div className="mt-0.5 rounded-md bg-primary/10 p-2 text-primary">{tab === "building" ? <Building2 className="h-4 w-4" /> : <MapPin className="h-4 w-4" />}</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-medium">{title}</span>{tab === "building" && !(item as Building).entrance_node_id && <Badge variant="outline">Sem rota</Badge>}{"active" in item && !item.active && <Badge variant="secondary">Inativo</Badge>}</div><p className="mt-1 break-words text-xs text-muted-foreground">{subtitle}</p></div><Button variant="ghost" size="icon" aria-label={`Editar ${title}`} onClick={() => startEdit(tab, item)} disabled={saving}><Pencil className="h-4 w-4" /></Button><Button variant="ghost" size="icon" aria-label={`Excluir ${title}`} onClick={() => setDeleting({ kind: tab, id: item.id, name: title, campusId: campus.id })} disabled={saving}><Trash2 className="h-4 w-4" /></Button></div>;
          })}</div>}
        </CardContent>
      </Card>}

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open) setDeleting(null); }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Excluir {deleting?.name}?</AlertDialogTitle><AlertDialogDescription>Esta ação remove o cadastro. Se ele estiver ligado a outros itens, talvez seja necessário remover essas ligações primeiro.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancelar</AlertDialogCancel><AlertDialogAction onClick={() => void remove()}>Excluir</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}

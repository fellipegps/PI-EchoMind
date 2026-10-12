"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, MapPin, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
  locationApi,
  type CampusLocation,
  type CampusLocationInput,
} from "@/lib/api";
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
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

const EMPTY_FORM: CampusLocationInput = {
  name: "",
  description: null,
  category: "outro",
  floor: null,
  building: null,
  x: 50,
  y: 50,
  active: true,
};

export function CampusLocationsManager() {
  const [locations, setLocations] = useState<CampusLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<CampusLocation | null>(null);
  const [deleting, setDeleting] = useState<CampusLocation | null>(null);
  const [form, setForm] = useState<CampusLocationInput>(EMPTY_FORM);
  const searchInput = useRef<HTMLInputElement>(null);
  const formTrigger = useRef<HTMLElement | null>(null);
  const deleteTrigger = useRef<HTMLElement | null>(null);

  const loadLocations = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setLocations(await locationApi.list());
    } catch {
      setError("Não foi possível carregar os locais. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    locationApi
      .list()
      .then((items) => {
        if (!cancelled) setLocations(items);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Não foi possível carregar os locais. Tente novamente.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredLocations = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    if (!term) return locations;
    return locations.filter((location) =>
      [location.name, location.category, location.building, location.floor]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("pt-BR")
        .includes(term)
    );
  }, [locations, search]);

  const openForm = (location?: CampusLocation) => {
    formTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setEditing(location ?? null);
    setForm(
      location
        ? {
            name: location.name,
            description: location.description,
            category: location.category,
            floor: location.floor,
            building: location.building,
            x: location.x,
            y: location.y,
            active: location.active,
          }
        : EMPTY_FORM
    );
    setDialogOpen(true);
  };

  const saveLocation = async () => {
    if (!form.name.trim() || !form.category.trim()) {
      toast.error("Preencha o nome e a categoria.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        category: form.category.trim(),
        description: form.description?.trim() || null,
        floor: form.floor?.trim() || null,
        building: form.building?.trim() || null,
      };
      if (editing) {
        const updated = await locationApi.update(editing.id, payload);
        setLocations((current) =>
          current.map((location) =>
            location.id === updated.id ? updated : location
          )
        );
        toast.success("Local atualizado!");
      } else {
        const created = await locationApi.create(payload);
        setLocations((current) =>
          [...current, created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"))
        );
        toast.success("Local cadastrado!");
      }
      setDialogOpen(false);
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : "Não foi possível salvar o local."
      );
    } finally {
      setSaving(false);
    }
  };

  const deleteLocation = async () => {
    if (!deleting) return;
    try {
      await locationApi.delete(deleting.id);
      setLocations((current) =>
        current.filter((location) => location.id !== deleting.id)
      );
      toast.success("Local excluído!");
      setDeleting(null);
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : "Não foi possível excluir o local."
      );
    }
  };

  return (
    <section className="min-w-0 space-y-6" aria-label="Gestão de locais">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1 space-y-2">
          <Label htmlFor="location-search">Pesquisar locais</Label>
          <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="location-search"
            ref={searchInput}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Pesquisar por nome, bloco, piso ou categoria..."
            className="pl-9"
          />
          </div>
        </div>
        <Button onClick={() => openForm()}>
          <Plus aria-hidden="true" className="h-4 w-4" /> Novo local
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/40">
          <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between md:p-6">
            <p className="min-w-0 text-sm text-foreground [overflow-wrap:anywhere]" role="alert">{error}</p>
            <Button variant="outline" onClick={() => void loadLocations()}>
              Tentar novamente
            </Button>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <Card><CardContent className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground" role="status" aria-label="Carregando locais">
          <Loader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />
          Carregando locais...
        </CardContent></Card>
      ) : filteredLocations.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center text-sm text-muted-foreground" role="status">
            <MapPin aria-hidden="true" className="size-6" />
            Nenhum local encontrado.
          </CardContent>
        </Card>
      ) : (
        <ul className="grid min-w-0 gap-4 xl:grid-cols-2" aria-label="Locais cadastrados">
          {filteredLocations.map((location) => (
            <li key={location.id} className="min-w-0">
            <article className="h-full" aria-labelledby={`location-heading-${location.id}`}>
            <Card className="h-full min-w-0">
              <CardContent className="flex min-w-0 flex-col gap-4 p-4 md:p-6">
                <div className="flex items-start gap-3">
                <div className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary">
                  <MapPin aria-hidden="true" className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 id={`location-heading-${location.id}`} className="min-w-0 text-base font-semibold [overflow-wrap:anywhere]">{location.name}</h2>
                    <Badge variant={location.active ? "success" : "secondary"}>
                      {location.active ? "Ativo" : "Inativo"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground [overflow-wrap:anywhere]">
                    {[location.category, location.building, location.floor]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {location.description && (
                    <p className="mt-3 line-clamp-2 text-sm [overflow-wrap:anywhere]">{location.description}</p>
                  )}
                  <p className="mt-2 text-xs text-muted-foreground">
                    Mapa esquemático: x {location.x} · y {location.y}
                  </p>
                </div>
                </div>
                <div className="flex justify-end gap-2 border-t pt-4">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => openForm(location)}
                    aria-label={`Editar ${location.name}`}
                  >
                    <Pencil aria-hidden="true" className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="text-destructive"
                    onClick={(event) => { deleteTrigger.current = event.currentTarget; setDeleting(location); }}
                    aria-label={`Excluir ${location.name}`}
                  >
                    <Trash2 aria-hidden="true" className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
            </article>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="grid max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl" onCloseAutoFocus={(event) => { event.preventDefault(); formTrigger.current?.focus(); }}>
          <DialogHeader className="pr-8 text-left">
            <DialogTitle>{editing ? "Editar local" : "Novo local"}</DialogTitle>
            <DialogDescription>
              As coordenadas de 0 a 100 posicionam o ponto no mapa esquemático.
            </DialogDescription>
          </DialogHeader>
          <div className="grid min-h-0 min-w-0 gap-5 overflow-y-auto px-1 py-1 sm:grid-cols-2 [&>div]:min-w-0" onFocusCapture={(event) => { if (event.target instanceof HTMLElement) event.target.scrollIntoView?.({ block: "nearest", inline: "nearest" }); }}>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="location-name">Nome</Label>
              <Input
                id="location-name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                maxLength={200}
                aria-required="true"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="location-category">Categoria</Label>
              <Input
                id="location-category"
                value={form.category}
                onChange={(event) => setForm({ ...form, category: event.target.value })}
                placeholder="Ex: laboratório"
                maxLength={100}
                aria-required="true"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="location-building">Bloco</Label>
              <Input
                id="location-building"
                value={form.building ?? ""}
                onChange={(event) => setForm({ ...form, building: event.target.value })}
                placeholder="Ex: Bloco F"
                maxLength={100}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="location-floor">Piso</Label>
              <Input
                id="location-floor"
                value={form.floor ?? ""}
                onChange={(event) => setForm({ ...form, floor: event.target.value })}
                placeholder="Ex: 2º andar"
                maxLength={50}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="location-x">Posição X</Label>
                <Input
                  id="location-x"
                  type="number"
                  min={0}
                  max={100}
                  step="0.1"
                  value={form.x}
                  onChange={(event) => setForm({ ...form, x: Number(event.target.value) })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="location-y">Posição Y</Label>
                <Input
                  id="location-y"
                  type="number"
                  min={0}
                  max={100}
                  step="0.1"
                  value={form.y}
                  onChange={(event) => setForm({ ...form, y: Number(event.target.value) })}
                />
              </div>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="location-description">Descrição</Label>
              <Textarea
                id="location-description"
                value={form.description ?? ""}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                maxLength={2000}
                rows={3}
                className="field-sizing-fixed max-h-48 min-h-24 resize-none overflow-y-auto"
              />
            </div>
            <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted p-4 sm:col-span-2">
              <div className="min-w-0 space-y-1">
                <Label htmlFor="location-active">Exibir no portal</Label>
                <p id="location-active-hint" className="text-sm text-muted-foreground">
                  Locais inativos ficam ocultos dos estudantes.
                </p>
              </div>
              <Switch
                id="location-active"
                aria-describedby="location-active-hint"
                className="shrink-0"
                checked={form.active}
                onCheckedChange={(active) => setForm({ ...form, active })}
              />
            </div>
          </div>
          <DialogFooter className="flex-col gap-2 sm:flex-row">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => void saveLocation()} disabled={saving} aria-busy={saving}>
              {saving && <Loader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />}
              {saving ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto" onCloseAutoFocus={(event) => { event.preventDefault(); (deleteTrigger.current?.isConnected ? deleteTrigger.current : searchInput.current)?.focus(); }}>
          <AlertDialogHeader className="text-left">
            <AlertDialogTitle>Excluir local?</AlertDialogTitle>
            <AlertDialogDescription tabIndex={0} aria-label="Efeito da exclusão" className="max-h-[40dvh] overflow-y-auto rounded-sm [overflow-wrap:anywhere] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              O local {deleting?.name} será removido do portal e da administração.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col gap-2 sm:flex-row">
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void deleteLocation()}
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

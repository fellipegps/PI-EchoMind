"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { MapPin, Pencil, Plus, Search, Trash2 } from "lucide-react";
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
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="relative flex-1">
          <span className="sr-only">Pesquisar locais</span>
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Pesquisar por nome, bloco, piso ou categoria..."
            className="pl-9"
          />
        </label>
        <Button onClick={() => openForm()}>
          <Plus className="h-4 w-4" /> Novo local
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/40">
          <CardContent className="flex items-center justify-between gap-3 p-4">
            <p className="text-sm text-destructive" role="alert">{error}</p>
            <Button variant="outline" onClick={() => void loadLocations()}>
              Tentar novamente
            </Button>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <p className="py-10 text-center text-muted-foreground" role="status">
          Carregando locais...
        </p>
      ) : filteredLocations.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            Nenhum local encontrado.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {filteredLocations.map((location) => (
            <Card key={location.id}>
              <CardContent className="flex gap-3 p-4">
                <div className="mt-1 rounded-lg bg-primary/10 p-2 text-primary">
                  <MapPin className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">{location.name}</h2>
                    <Badge variant={location.active ? "default" : "secondary"}>
                      {location.active ? "Ativo" : "Inativo"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {[location.category, location.building, location.floor]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {location.description && (
                    <p className="mt-2 line-clamp-2 text-sm">{location.description}</p>
                  )}
                  <p className="mt-2 text-xs text-muted-foreground">
                    Mapa: x {location.x} · y {location.y}
                  </p>
                </div>
                <div className="flex flex-col gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => openForm(location)}
                    aria-label={`Editar ${location.name}`}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-destructive"
                    onClick={() => setDeleting(location)}
                    aria-label={`Excluir ${location.name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar local" : "Novo local"}</DialogTitle>
            <DialogDescription>
              As coordenadas de 0 a 100 posicionam o ponto no mapa esquemático.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="location-name">Nome</Label>
              <Input
                id="location-name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                maxLength={200}
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
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3 sm:col-span-2">
              <div>
                <Label htmlFor="location-active">Exibir no portal</Label>
                <p className="text-sm text-muted-foreground">
                  Locais inativos ficam ocultos dos estudantes.
                </p>
              </div>
              <Switch
                id="location-active"
                checked={form.active}
                onCheckedChange={(active) => setForm({ ...form, active })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => void saveLocation()} disabled={saving}>
              {saving ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir local?</AlertDialogTitle>
            <AlertDialogDescription>
              O local {deleting?.name} será removido do portal e da administração.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
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
    </div>
  );
}

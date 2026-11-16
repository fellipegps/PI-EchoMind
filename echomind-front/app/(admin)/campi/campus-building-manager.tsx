import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { geoCampusApi, type Building, type IndoorSpace } from "@/lib/geocampus-api";
import { PlaceMediaManager } from "./place-media-manager";
import { PlaceQrCode } from "./place-qr-code";

function SpaceForm({ building, space, onChanged, onClose }: {
  building: Building;
  space: IndoorSpace | undefined;
  onChanged: () => Promise<void>;
  onClose: () => void;
}) {
  const [saving, setSaving] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const kind = String(form.get("kind") ?? "").trim();
    if (name.length < 2 || kind.length < 2) {
      toast.error("Informe um nome e um tipo com pelo menos dois caracteres.");
      return;
    }
    const details = {
      name, kind, floor: String(form.get("floor") ?? "").trim() || null,
      description: String(form.get("description") ?? "").trim() || null,
      active: form.has("active"),
    };
    setSaving(true);
    try {
      if (space) await geoCampusApi.spaces.update(building.campus_id, space.id, details);
      else await geoCampusApi.spaces.create(building.campus_id, building.id, details);
      toast.success("Local interno salvo.");
      await onChanged().catch(() => {});
      onClose();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Não foi possível salvar o local interno.");
    } finally {
      setSaving(false);
    }
  }

  return <form className="grid gap-3 rounded-lg border p-4" onSubmit={(event) => void save(event)}>
    <h4 className="font-medium">{space ? "Editar local interno" : "Novo local interno"}</h4>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-2 text-sm">Nome do local interno<Input name="name" defaultValue={space?.name} required minLength={2} maxLength={200} disabled={saving} /></label>
      <label className="grid gap-2 text-sm">Tipo<Input name="kind" defaultValue={space?.kind ?? "sala"} required minLength={2} maxLength={100} disabled={saving} /></label>
      <label className="grid gap-2 text-sm">Piso<Input name="floor" defaultValue={space?.floor ?? ""} maxLength={50} disabled={saving} /></label>
    </div>
    <label className="grid gap-2 text-sm">Descrição do local interno<Textarea name="description" defaultValue={space?.description ?? ""} maxLength={2000} disabled={saving} /></label>
    <label className="flex items-center gap-2 text-sm"><input name="active" type="checkbox" defaultChecked={space?.active ?? true} disabled={saving} />Visível na ficha pública</label>
    <div className="flex flex-wrap gap-2"><Button type="submit" disabled={saving}>Salvar local interno</Button>
      <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancelar</Button></div>
  </form>;
}

function BuildingDetails({ building, spaces, publicSlug, onChanged }: {
  building: Building;
  spaces: IndoorSpace[];
  publicSlug: string;
  onChanged: () => Promise<void>;
}) {
  const [renaming, setRenaming] = useState(false);
  const [spaceEditor, setSpaceEditor] = useState<string | "new" | null>(null);
  const [photoSpaceId, setPhotoSpaceId] = useState<string | null>(null);
  const editing = spaces.find((space) => space.id === spaceEditor);
  const photoSpace = spaces.find((space) => space.id === photoSpaceId);

  async function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (renaming) return;
    const name = String(new FormData(event.currentTarget).get("name") ?? "").trim();
    if (name.length < 2) {
      toast.error("Informe um nome com pelo menos dois caracteres.");
      return;
    }
    if (name === building.name) return;
    setRenaming(true);
    try {
      await geoCampusApi.buildings.rename(building.campus_id, building.id, name);
      toast.success("Nome do bloco atualizado.");
      await onChanged().catch(() => {});
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Não foi possível renomear o bloco.");
    } finally {
      setRenaming(false);
    }
  }

  return <>
    <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => void rename(event)}>
      <div className="min-w-0 flex-1 space-y-2">
        <Label htmlFor="campus-building-name">Nome do bloco</Label>
        <Input key={building.name} id="campus-building-name" name="name" defaultValue={building.name}
          required minLength={2} maxLength={200} disabled={renaming} />
      </div>
      <Button type="submit" disabled={renaming}>Salvar nome do bloco</Button>
    </form>
    <PlaceMediaManager campusId={building.campus_id} placeType="building" placeId={building.id} placeName={building.name}
      photos={building.photos} onChanged={onChanged} />
    <section className="grid gap-3 border-t pt-4" aria-labelledby="indoor-places-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="indoor-places-title" className="font-semibold">Locais internos</h3>
        <Button type="button" variant="outline" onClick={() => setSpaceEditor("new")}>Novo local interno</Button>
      </div>
      {spaceEditor && <SpaceForm key={spaceEditor} space={editing} building={building} onChanged={onChanged}
        onClose={() => setSpaceEditor(null)} />}
      {spaces.length ? <ul className="grid gap-2">
        {spaces.map((space) => <li key={space.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
          <div className="min-w-0 [overflow-wrap:anywhere]">
            <p className="font-medium">{space.name}{space.floor ? " · " + space.floor : ""}</p>
            {space.description && <p className="text-sm text-muted-foreground">{space.description}</p>}
            {!space.active && <p className="text-xs text-muted-foreground">Oculto no portal</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" type="button" onClick={() => setSpaceEditor(space.id)} aria-label={"Editar " + space.name}>Editar</Button>
            <Button variant="outline" type="button" onClick={() => setPhotoSpaceId(space.id)}
              aria-label={"Fotos e QR Code de " + space.name}>Fotos e QR Code</Button>
          </div>
        </li>)}
      </ul> : <p className="text-sm text-muted-foreground">Nenhum local interno cadastrado neste bloco.</p>}
      {photoSpace && <div className="grid items-start gap-3 lg:grid-cols-2">
        <PlaceMediaManager key={photoSpace.id} campusId={building.campus_id} placeType="space" placeId={photoSpace.id}
          placeName={photoSpace.name} photos={photoSpace.photos} onChanged={onChanged} />
        <PlaceQrCode key={photoSpace.public_code} publicSlug={publicSlug} placeType="space"
          publicCode={photoSpace.public_code} placeName={photoSpace.name} />
      </div>}
    </section>
  </>;
}

export function CampusBuildingManager({ buildings, spaces, buildingId, onSelect, publicSlug, onChanged }: {
  buildings: Building[];
  spaces: IndoorSpace[];
  buildingId: string;
  onSelect: (id: string) => void;
  publicSlug: string;
  onChanged: () => Promise<void>;
}) {
  const building = buildings.find((item) => item.id === buildingId);
  return <Card id="campus-building-manager">
    <CardHeader><CardTitle><h2>Blocos e locais internos</h2></CardTitle></CardHeader>
    <CardContent className="grid min-w-0 gap-4">
      {buildings.length ? <>
        <div className="grid gap-2">
          <Label htmlFor="campus-building-select">Bloco</Label>
          <select id="campus-building-select" className="min-h-11 rounded-lg border border-input bg-card px-3 text-sm"
            value={building?.id ?? ""} onChange={(event) => onSelect(event.target.value)}>
            <option value="">Selecione um bloco</option>
            {buildings.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
        {building && <BuildingDetails key={building.id} building={building}
          spaces={spaces.filter((space) => space.building_id === building.id)} publicSlug={publicSlug} onChanged={onChanged} />}
      </> : <p className="text-sm text-muted-foreground">A equipe EchoMind ainda não configurou blocos neste campus.</p>}
    </CardContent>
  </Card>;
}

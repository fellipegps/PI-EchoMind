"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { Loader2, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { geoCampusApi, type PlacePhoto, type PlaceType } from "@/lib/geocampus-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  campusId: string;
  placeType: PlaceType;
  placeId: string;
  placeName: string;
  photos: PlacePhoto[];
  onChanged: () => Promise<void>;
};

function PhotoPreview({ campusId, placeType, placeId, photo, placeName }: Omit<Props, "photos" | "onChanged"> & { photo: PlacePhoto }) {
  const [preview, setPreview] = useState({ url: "", failed: false });
  useEffect(() => {
    let active = true;
    let objectUrl = "";
    void geoCampusApi.photos.content(campusId, placeType, placeId, photo.id)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setPreview({ url: objectUrl, failed: false });
      })
      .catch(() => { if (active) setPreview({ url: "", failed: true }); });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [campusId, placeType, placeId, photo.id]);

  if (preview.failed) return <p role="status" className="p-4 text-sm text-muted-foreground">Prévia indisponível.</p>;
  if (!preview.url) return <p role="status" className="p-4 text-sm text-muted-foreground">Carregando foto...</p>;
  return <Image src={preview.url} alt={photo.caption || "Referência visual de " + placeName} width={420} height={280} unoptimized className="h-40 w-full rounded-md object-contain" />;
}

export function PlaceMediaManager({ campusId, placeType, placeId, placeName, photos, onChanged }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const operationPending = useRef(false);
  const inputId = "photos-" + placeId;

  const upload = async () => {
    if (!files.length || operationPending.current) return;
    if (files.some((file) => file.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type))) {
      toast.error("Escolha fotos JPEG, PNG ou WebP de até 5 MiB cada.");
      return;
    }
    operationPending.current = true;
    setBusy(true);
    let uploaded = 0;
    try {
      for (const file of files) {
        await geoCampusApi.photos.upload(campusId, placeType, placeId, file, caption.trim() || undefined);
        uploaded += 1;
      }
      toast.success(uploaded + " foto(s) adicionada(s).");
      setFiles([]);
      setCaption("");
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      toast.error((error instanceof Error ? error.message : "Não foi possível enviar as fotos.") + (uploaded ? " " + uploaded + " foto(s) já foram salvas." : ""));
      // A retry sends only the files that were not accepted by the server.
      setFiles((current) => current.slice(uploaded));
      if (fileInput.current) fileInput.current.value = "";
    } finally {
      try {
        if (uploaded) await onChanged();
      } catch {
        toast.error("As fotos foram salvas, mas a lista não pôde ser atualizada. Abra este local novamente.");
      } finally {
        operationPending.current = false;
        setBusy(false);
      }
    }
  };

  const remove = async (photoId: string) => {
    if (operationPending.current) return;
    operationPending.current = true;
    setDeleting(photoId);
    try {
      await geoCampusApi.photos.delete(campusId, placeType, placeId, photoId);
      await onChanged();
      toast.success("Foto removida.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Não foi possível remover a foto.");
    } finally {
      operationPending.current = false;
      setDeleting("");
    }
  };

  return (
    <section aria-label={"Fotos de " + placeName} className="min-w-0 space-y-4">
      <div className="space-y-2">
        <Label htmlFor={inputId}>Adicionar fotos de referência</Label>
        <Input id={inputId} ref={fileInput} type="file" multiple accept="image/jpeg,image/png,image/webp" disabled={busy || Boolean(deleting)} aria-describedby={inputId + "-help"} onChange={(event) => setFiles(Array.from(event.target.files || []))} />
        <p id={inputId + "-help"} className="text-sm text-muted-foreground">JPEG, PNG ou WebP, até 5 MiB e 16 megapixels por foto. Você pode selecionar várias imagens.</p>
        {files.length > 0 && <p role="status" className="text-sm">{files.length} foto(s) para enviar.</p>}
      </div>
      <div className="space-y-2">
        <Label htmlFor={inputId + "-caption"}>Descrição das fotos selecionadas (opcional)</Label>
        <Input id={inputId + "-caption"} value={caption} maxLength={300} onChange={(event) => setCaption(event.target.value)} disabled={busy || Boolean(deleting)} placeholder="Ex.: fachada vista da praça central" />
      </div>
      <Button onClick={() => void upload()} disabled={!files.length || busy || Boolean(deleting)} aria-busy={busy}>
        {busy ? <Loader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" /> : <Upload aria-hidden="true" className="size-4" />}
        {busy ? "Enviando fotos..." : "Enviar fotos"}
      </Button>
      {!photos.length ? <p className="text-sm text-muted-foreground">Nenhuma foto cadastrada neste local.</p> : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {photos.map((photo, index) => (
            <li key={photo.id} className="min-w-0 space-y-2 rounded-lg border p-3">
              <PhotoPreview campusId={campusId} placeType={placeType} placeId={placeId} placeName={placeName} photo={photo} />
              <p className="text-sm [overflow-wrap:anywhere]">{photo.caption || "Foto " + (index + 1)}</p>
              <Button variant="outline" size="sm" className="text-destructive" disabled={busy || Boolean(deleting)} onClick={() => void remove(photo.id)} aria-label={"Remover foto " + (index + 1) + " de " + placeName}>
                <Trash2 aria-hidden="true" className="size-4" />{deleting === photo.id ? "Removendo..." : "Remover foto"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

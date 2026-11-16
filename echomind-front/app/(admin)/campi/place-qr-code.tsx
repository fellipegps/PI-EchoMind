"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Copy, Download, Printer } from "lucide-react";
import { toast } from "sonner";
import { publicPlaceHref, type PlaceType } from "@/lib/geocampus-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = { publicSlug: string; placeType: PlaceType; publicCode: string; placeName: string };

export function PlaceQrCode({ publicSlug, placeType, publicCode, placeName }: Props) {
  const href = publicSlug && publicCode ? publicPlaceHref(publicSlug, placeType, publicCode) : "";
  const [qr, setQr] = useState({ href: "", url: "", image: "", error: "" });
  const current = qr.href === href ? qr : { url: "", image: "", error: "" };
  useEffect(() => {
    if (!href) return;
    let active = true;
    const url = window.location.origin + href;
    void QRCode.toDataURL(url, { width: 512, margin: 3, errorCorrectionLevel: "M", color: { dark: "#000000", light: "#ffffff" } })
      .then((image) => { if (active) setQr({ href, url, image, error: "" }); })
      .catch(() => { if (active) setQr({ href, url, image: "", error: "Não foi possível gerar o QR Code. Tente abrir este local novamente." }); });
    return () => { active = false; };
  }, [href]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(current.url);
      toast.success("Link do local copiado.");
    } catch {
      toast.error("Não foi possível copiar o link.");
    }
  };

  const print = () => {
    if (!current.image) return;
    const target = window.open("", "_blank", "width=640,height=760");
    if (!target) {
      toast.error("Permita a abertura da janela para imprimir o QR Code.");
      return;
    }
    target.opener = null;
    target.document.title = "QR Code — " + placeName;
    const style = target.document.createElement("style");
    style.textContent = "body{font:18px Arial,sans-serif;text-align:center;padding:24px;color:#000;background:#fff}img{display:block;width:320px;max-width:100%;margin:16px auto}p{overflow-wrap:anywhere;font-size:14px}@page{margin:20mm}";
    target.document.head.appendChild(style);
    const title = target.document.createElement("h1");
    title.textContent = placeName;
    const instruction = target.document.createElement("p");
    instruction.textContent = "Escaneie para ver a descrição e as fotos deste local no EchoMind.";
    const image = target.document.createElement("img");
    image.alt = "QR Code de " + placeName;
    image.onload = () => { target.focus(); target.print(); };
    image.src = current.image;
    const address = target.document.createElement("p");
    address.textContent = current.url;
    target.document.body.replaceChildren(title, instruction, image, address);
  };

  return (
    <section aria-label={"QR Code de " + placeName} className="min-w-0 space-y-4 rounded-lg border border-border p-4 sm:p-5">
      <h3 className="font-medium">Ficha pública do local</h3>
      {!href ? <p role="status" className="text-sm">Abra Configurações e confira o endereço público da instituição para gerar o QR Code.</p> : <>
        <div className="min-w-0 space-y-2">
          <Label htmlFor={"place-link-" + publicCode}>Link público do local</Label>
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
            <Input id={"place-link-" + publicCode} value={current.url} title={current.url} readOnly className="min-w-0 truncate" />
            <Button type="button" variant="outline" size="icon" disabled={!current.url} onClick={() => void copyLink()} aria-label="Copiar link" title="Copiar link"><Copy aria-hidden="true" /></Button>
          </div>
        </div>
        {current.error && <p role="alert" className="text-sm text-destructive">{current.error}</p>}
        {current.image ? <div className="grid place-items-center rounded-md bg-muted/40 p-4">
          <Image src={current.image} width={160} height={160} unoptimized alt={"QR Code de " + placeName} className="h-auto max-w-full rounded-md border bg-white p-2" />
        </div> : !current.error && <p role="status" className="text-sm">Gerando QR Code...</p>}
        <div className="flex flex-wrap justify-center gap-2">
          <Button disabled={!current.image} onClick={print}><Printer aria-hidden="true" className="size-4" />Imprimir QR Code</Button>
          {current.image && <Button asChild variant="outline"><a href={current.image} download={"local-" + publicCode + ".png"}><Download aria-hidden="true" className="size-4" />Baixar QR Code</a></Button>}
          {current.url && <Button asChild variant="outline"><a href={current.url} target="_blank" rel="noopener noreferrer">Abrir ficha</a></Button>}
        </div>
      </>}
    </section>
  );
}

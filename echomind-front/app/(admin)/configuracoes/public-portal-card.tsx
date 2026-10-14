"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { Copy, Download, ExternalLink, LinkIcon, Loader2, QrCode } from "lucide-react";
import QRCode from "qrcode";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type PublicPortalCardProps = {
  publicSlug: string;
};

export function PublicPortalCard({ publicSlug }: PublicPortalCardProps) {
  const normalizedSlug = publicSlug.trim();
  const [qrState, setQrState] = useState<{
    slug: string;
    publicUrl: string;
    dataUrl: string;
    error: string;
  }>({ slug: "", publicUrl: "", dataUrl: "", error: "" });
  const stateMatchesSlug = qrState.slug === normalizedSlug;
  const publicUrl = stateMatchesSlug ? qrState.publicUrl : "";
  const qrDataUrl = stateMatchesSlug ? qrState.dataUrl : "";
  const qrError = stateMatchesSlug ? qrState.error : "";

  useEffect(() => {
    if (!normalizedSlug || typeof window === "undefined") return;

    const url = `${window.location.origin}/p/${encodeURIComponent(normalizedSlug)}`;
    let active = true;

    QRCode.toDataURL(url, {
      errorCorrectionLevel: "M",
      margin: 2,
      width: 256,
      color: { dark: "#172554", light: "#ffffff" },
    })
      .then((dataUrl) => {
        if (active) {
          setQrState({
            slug: normalizedSlug,
            publicUrl: url,
            dataUrl,
            error: "",
          });
        }
      })
      .catch(() => {
        if (active) {
          setQrState({
            slug: normalizedSlug,
            publicUrl: url,
            dataUrl: "",
            error: "Não foi possível gerar o QR Code agora.",
          });
        }
      });

    return () => {
      active = false;
    };
  }, [normalizedSlug]);

  const copyUrl = async () => {
    if (!publicUrl) return;
    try {
      await navigator.clipboard.writeText(publicUrl);
      toast.success("Link do portal copiado!");
    } catch {
      toast.error("Não foi possível copiar o link.");
    }
  };

  const openPortal = () => {
    if (publicUrl) window.open(publicUrl, "_blank", "noopener,noreferrer");
  };

  return (
    <Card className="gap-5">
      <CardHeader className="px-4 md:px-6">
        <div className="flex items-start gap-3">
          <span className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary"><LinkIcon className="h-5 w-5" aria-hidden="true" /></span>
          <CardTitle><h2 className="text-lg">Portal público da instituição</h2></CardTitle>
        </div>
        <CardDescription>
          Compartilhe o link ou o QR Code com estudantes para abrir o portal da instituição.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid min-w-0 gap-6 px-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:px-6">
        <div className="min-w-0 space-y-3">
          <Label htmlFor="public-portal-url">URL do portal público</Label>
          <Input
            id="public-portal-url"
            value={publicUrl}
            readOnly
            aria-describedby="public-portal-state"
            className="min-w-0 bg-background font-mono text-sm"
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void copyUrl()} disabled={!publicUrl}>
              <Copy className="h-4 w-4" aria-hidden="true" />
              Copiar link
            </Button>
            <Button onClick={openPortal} disabled={!publicUrl}>
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              Abrir portal
            </Button>
            {qrDataUrl && (
              <Button variant="outline" asChild>
                <a href={qrDataUrl} download={`portal-${publicSlug}.png`}>
                  <Download className="h-4 w-4" aria-hidden="true" />
                  Baixar QR
                </a>
              </Button>
            )}
          </div>
          <p id="public-portal-state" role="status" className="text-sm text-muted-foreground [overflow-wrap:anywhere]">
            {!normalizedSlug ? "Salve a configuração institucional para gerar o endereço público." : qrDataUrl ? "QR Code pronto para compartilhar. O download é gerado neste dispositivo." : qrError ? "O link continua disponível. Tente gerar o QR Code novamente mais tarde." : "Gerando QR Code…"}
          </p>
          {qrError && <p className="text-sm text-destructive" role="alert">{qrError}</p>}
        </div>

        <div className="flex h-44 w-44 items-center justify-center justify-self-center rounded-xl border bg-white p-2 md:justify-self-end">
          {qrDataUrl ? (
            <Image
              src={qrDataUrl}
              alt="QR Code do portal público"
              width={160}
              height={160}
              unoptimized
            />
          ) : normalizedSlug && !qrError ? (
            <Loader2 className="h-7 w-7 animate-spin text-[#172554] motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <QrCode className="h-12 w-12 text-[#172554]" aria-hidden="true" />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

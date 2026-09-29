"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { Copy, Download, ExternalLink, LinkIcon, Loader2, QrCode } from "lucide-react";
import QRCode from "qrcode";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

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
    <Card className="bg-card">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2 text-primary">
          <LinkIcon className="h-5 w-5" />
          <CardTitle className="text-lg">Portal público da instituição</CardTitle>
        </div>
        <CardDescription>
          Compartilhe este endereço com estudantes. O link não expõe o identificador interno do tenant.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5 md:grid-cols-[1fr_auto] md:items-center">
        <div className="space-y-3">
          <Input
            aria-label="URL do portal público"
            value={publicUrl}
            readOnly
            className="bg-background font-mono text-sm"
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void copyUrl()} disabled={!publicUrl}>
              <Copy className="h-4 w-4" />
              Copiar link
            </Button>
            <Button onClick={openPortal} disabled={!publicUrl}>
              <ExternalLink className="h-4 w-4" />
              Abrir portal
            </Button>
            {qrDataUrl && (
              <Button variant="outline" asChild>
                <a href={qrDataUrl} download={`portal-${publicSlug}.png`}>
                  <Download className="h-4 w-4" />
                  Baixar QR
                </a>
              </Button>
            )}
          </div>
          {!publicSlug && (
            <p className="text-sm text-muted-foreground">
              Salve a configuração institucional para gerar o endereço público.
            </p>
          )}
          {qrError && <p className="text-sm text-destructive" role="alert">{qrError}</p>}
        </div>

        <div className="flex h-44 w-44 items-center justify-center rounded-xl border bg-white p-2">
          {qrDataUrl ? (
            <Image
              src={qrDataUrl}
              alt="QR Code do portal público"
              width={160}
              height={160}
              unoptimized
            />
          ) : publicSlug && !qrError ? (
            <Loader2 className="h-7 w-7 animate-spin text-primary" aria-label="Gerando QR Code" />
          ) : (
            <QrCode className="h-12 w-12 text-muted-foreground" aria-hidden="true" />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

"use client";
import { useState } from "react";
import { PublicPortal } from "@/app/(public)/components/public-portal";
import { Button } from "@/components/ui/button";

export function MapVerification() {
  const [mounted, setMounted] = useState(true);
  return <>
    <section aria-label="Guia visual de teste" className="relative z-40 space-y-3 border-b border-border bg-card p-4 text-foreground lg:ml-56">
      <p className="text-sm font-medium">DS-06 · Guia visual · somente desenvolvimento</p>
      <p className="text-sm">Abra blocos, espaços e referências para consultar suas fichas e fotos.</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => setMounted(value => !value)}>{mounted ? "Desmontar portal de teste" : "Montar portal de teste"}</Button>
      </div>
    </section>
    {mounted && <PublicPortal publicSlug="ds06-fixture" initialTab="locais" />}
  </>;
}

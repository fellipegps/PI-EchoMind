"use client";
import { useState } from "react";
import { GeoCampusManager } from "@/app/(admin)/campi/geo-campus-manager";
import { Button } from "@/components/ui/button";
import { ModeToggle } from "@/components/mode-toggle";

export function CampusVerification() {
  const [mounted, setMounted] = useState(true);
  return <main className="space-y-6 bg-background p-4 text-foreground md:p-6">
    <section aria-label="Guia visual DS-14" className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-4"><h1 className="font-semibold">DS-14 · Guia visual · desenvolvimento</h1><ModeToggle /></div>
      <p>Cadastro de blocos, espaços internos, pontos de referência e fotos.</p><div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => setMounted(value => !value)}>{mounted ? "Desmontar editor" : "Montar editor"}</Button>
      </div>
    </section>
    {mounted && <GeoCampusManager />}
  </main>;
}

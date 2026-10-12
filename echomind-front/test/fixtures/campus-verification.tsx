"use client";
// Development-only GPS mock. Never invokes native geolocation.
import { useEffect, useRef, useState } from "react";
import { GeoCampusManager } from "@/app/(admin)/campi/geo-campus-manager";
import { Button } from "@/components/ui/button";
import { ModeToggle } from "@/components/mode-toggle";

export function CampusVerification() {
  const mode = useRef("accepted");
  const [ready, setReady] = useState(false);
  const [mounted, setMounted] = useState(true);
  const [status, setStatus] = useState("Chamadas: 0 · acompanhamento: 0");
  const configure = useRef<(next: string) => void>(() => {});
  useEffect(() => {
    const descriptor = Object.getOwnPropertyDescriptor(navigator, "geolocation"); let calls = 0;
    const mock = {
      getCurrentPosition(success: PositionCallback, error?: PositionErrorCallback | null, options?: PositionOptions) {
        setStatus(`Chamadas: ${++calls} · acompanhamento: 0 · alta precisão: ${options?.enableHighAccuracy} · timeout: ${options?.timeout}`);
        if (mode.current === "accepted") success({ coords: { latitude: -16.3281234567, longitude: -48.9531234567 } } as GeolocationPosition);
        else error?.({ code: 1 } as GeolocationPositionError);
      },
      watchPosition() { throw new Error("DS-14 não permite acompanhamento contínuo."); },
      clearWatch() {},
    };
    configure.current = (next) => { mode.current = next; Object.defineProperty(navigator, "geolocation", { configurable: true, value: next === "unavailable" ? undefined : mock }); };
    configure.current("accepted"); queueMicrotask(() => setReady(true));
    return () => { if (descriptor) Object.defineProperty(navigator, "geolocation", descriptor); else Reflect.deleteProperty(navigator, "geolocation"); };
  }, []);
  return <main className="space-y-6 bg-background p-4 text-foreground md:p-6">
    <section aria-label="Simulação GPS DS-14" className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-4"><h1 className="font-semibold">DS-14 · GPS fictício · desenvolvimento</h1><ModeToggle /></div>
      <p role="status">{status}</p><div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => configure.current("accepted")}>Preparar GPS aceito</Button>
        <Button variant="outline" onClick={() => configure.current("denied")}>Preparar GPS negado</Button>
        <Button variant="outline" onClick={() => configure.current("unavailable")}>Preparar GPS indisponível</Button>
        <Button variant="outline" onClick={() => setMounted(value => !value)}>{mounted ? "Desmontar editor" : "Montar editor"}</Button>
      </div>
    </section>
    {ready && mounted && <GeoCampusManager />}
  </main>;
}

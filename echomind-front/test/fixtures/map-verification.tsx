"use client";
// Development-only UI harness; never obtains a real position or calls the native GPS.
import { useEffect, useRef, useState } from "react";
import { PublicPortal } from "@/app/(public)/components/public-portal";
import { Button } from "@/components/ui/button";

type Watch = { success: PositionCallback; error?: PositionErrorCallback | null };
export function MapVerification() {
  const watches = useRef(new Map<number, Watch>());
  const sequence = useRef(0);
  const timestamp = useRef(1000);
  const [ready, setReady] = useState(false);
  const [counts, setCounts] = useState({ started: 0, cleared: 0, active: 0 });
  const [mounted, setMounted] = useState(true);
  useEffect(() => {
    const descriptor = Object.getOwnPropertyDescriptor(navigator, "geolocation");
    const mock = {
      watchPosition(success: PositionCallback, error?: PositionErrorCallback | null) {
        const id = ++sequence.current;
        watches.current.set(id, { success, error });
        setCounts(c => ({ ...c, started: c.started + 1, active: watches.current.size }));
        return id;
      },
      clearWatch(id: number) {
        watches.current.delete(id);
        setCounts(c => ({ ...c, cleared: c.cleared + 1, active: watches.current.size }));
      },
      getCurrentPosition() { throw new Error("Esta fixture só permite acompanhamento simulado."); },
    };
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: mock });
    queueMicrotask(() => setReady(true));
    const activeWatches = watches.current;
    return () => {
      activeWatches.clear();
      if (descriptor) Object.defineProperty(navigator, "geolocation", descriptor);
      else Reflect.deleteProperty(navigator, "geolocation");
    };
  }, []);
  const position = (lat: number, lng: number, accuracy: number) => {
    const value = { coords: { latitude: lat, longitude: lng, accuracy }, timestamp: ++timestamp.current } as GeolocationPosition;
    for (const watch of watches.current.values()) watch.success(value);
  };
  const fail = (code: number) => { for (const watch of watches.current.values()) watch.error?.({ code } as GeolocationPositionError); };
  return <>
    <section aria-label="Controles da simulação GPS" className="relative z-40 space-y-3 border-b border-border bg-card p-4 text-foreground lg:ml-56">
      <p className="text-sm font-medium">DS-06 · GPS fictício · somente desenvolvimento</p>
      <p role="status" className="text-sm">Observadores iniciados: {counts.started} · liberados: {counts.cleared} · ativos: {counts.active}</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => position(-23.5505, -46.6335, 12)}>Sinal preciso simulado</Button>
        <Button variant="outline" onClick={() => position(-23.5505, -46.633499, 12)}>Pequeno salto simulado</Button>
        <Button variant="outline" onClick={() => position(-23.5505, -46.6333, 30)}>Movimento simulado</Button>
        <Button variant="outline" onClick={() => position(-23.5505, -46.6333, 90)}>Sinal impreciso simulado</Button>
        <Button variant="outline" onClick={() => position(-23.5504, -46.6332, 10)}>Chegada simulada</Button>
        <Button variant="outline" onClick={() => fail(1)}>Negação simulada</Button>
        <Button variant="outline" onClick={() => fail(2)}>Indisponibilidade simulada</Button>
        <Button variant="outline" onClick={() => fail(3)}>Timeout simulado</Button>
        <Button variant="outline" onClick={() => setMounted(value => !value)}>{mounted ? "Desmontar portal de teste" : "Montar portal de teste"}</Button>
      </div>
    </section>
    {ready && mounted && <PublicPortal publicSlug="ds06-fixture" />}
  </>;
}

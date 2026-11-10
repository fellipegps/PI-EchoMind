import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => {
  const handlers = new Map<string, (event?: unknown) => void>();
  const markerHandlers = new Map<string, () => void>();
  const map = { on: vi.fn((name, callback) => { handlers.set(name, callback); }), remove: vi.fn(), invalidateSize: vi.fn(), setView: vi.fn(), getZoom: vi.fn(() => 18) };
  const layer = { addTo: vi.fn().mockReturnThis(), bindTooltip: vi.fn().mockReturnThis(), clearLayers: vi.fn() };
  const marker = { ...layer, on: vi.fn((name, callback) => { markerHandlers.set(name, callback); }), getLatLng: vi.fn(() => ({ lat: -16.123456789, lng: -48.987654321 })) };
  return { handlers, markerHandlers, map, layer, marker, create: vi.fn(() => map), polyline: vi.fn(() => layer), circleMarker: vi.fn(() => layer), createMarker: vi.fn(() => marker) };
});
vi.mock("leaflet", () => ({ map: fake.create, tileLayer: () => fake.layer, layerGroup: () => fake.layer, circleMarker: fake.circleMarker, polyline: fake.polyline, marker: fake.createMarker, divIcon: vi.fn(), control: { zoom: () => fake.layer, layers: () => fake.layer } }));
import { GeoCampusMap } from "./geo-campus-map";

const props = { center: { lat: -16.328, lng: -48.953 }, zoom: 17, buildings: [], landmarks: [], draftPoint: null, focusPoint: null };
let observerCallback: ResizeObserverCallback;
let disconnect: ReturnType<typeof vi.fn>;
let frames: Map<number, FrameRequestCallback>;
let frameId: number;
beforeEach(() => {
  vi.clearAllMocks(); fake.handlers.clear(); fake.markerHandlers.clear(); frames = new Map(); frameId = 0;
  disconnect = vi.fn();
  vi.stubGlobal("ResizeObserver", class { constructor(callback: ResizeObserverCallback) { observerCallback = callback; } observe() {} disconnect = disconnect; });
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => { frames.set(++frameId, callback); return frameId; }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn((id: number) => { frames.delete(id); }));
});
afterEach(() => vi.unstubAllGlobals());

describe("GeoCampusMap lifecycle and geography", () => {
  it("preserva instância e vista ao editar rascunho; click e arraste entregam precisão integral", async () => {
    const pick = vi.fn(); const { rerender } = render(<GeoCampusMap {...props} onPickPoint={pick} />);
    await waitFor(() => expect(fake.create).toHaveBeenCalledTimes(1));
    const before = fake.map.setView.mock.calls.length;
    rerender(<GeoCampusMap {...props} center={{ ...props.center }} draftPoint={{ lat: 1, lng: 2 }} onPickPoint={pick} />);
    expect(fake.create).toHaveBeenCalledTimes(1); expect(fake.map.setView).toHaveBeenCalledTimes(before);
    act(() => fake.handlers.get("click")?.({ latlng: { lat: -16.123456789, lng: -48.987654321 } }));
    expect(pick).toHaveBeenLastCalledWith({ lat: -16.123456789, lng: -48.987654321 });
    act(() => fake.markerHandlers.get("dragend")?.());
    expect(pick).toHaveBeenLastCalledWith({ lat: -16.123456789, lng: -48.987654321 });
  });
  it("reflow invalida dimensões sem pan e desmontagem cancela frames antes de remover mapa", async () => {
    const { unmount } = render(<GeoCampusMap {...props} />);
    await waitFor(() => expect(fake.create).toHaveBeenCalledTimes(1));
    act(() => { for (const callback of frames.values()) callback(0); frames.clear(); });
    act(() => observerCallback([], {} as ResizeObserver));
    act(() => { for (const callback of frames.values()) callback(0); frames.clear(); });
    expect(fake.map.invalidateSize).toHaveBeenLastCalledWith({ pan: false });
    act(() => observerCallback([], {} as ResizeObserver));
    const queued = [...frames.values()]; const before = fake.map.invalidateSize.mock.calls.length;
    unmount(); expect(disconnect).toHaveBeenCalled(); expect(fake.map.remove).toHaveBeenCalledTimes(1); expect(frames.size).toBe(0);
    queued.forEach(callback => callback(0));
    expect(fake.map.invalidateSize).toHaveBeenCalledTimes(before);
  });
  it("mostra blocos e referências com texto seguro sem desenhar caminhos", async () => {
    const landmark = { id: "ref", campus_id: "c", public_code: "ref", lat: 1, lng: 2, name: "<script>praça</script>", description: null, active: true, photos: [] };
    const building = { id: "block", campus_id: "c", public_code: "block", name: "Bloco A", description: null, category: "bloco", entrance_lat: 3, entrance_lng: 4, active: false, photos: [] };
    render(<GeoCampusMap {...props} landmarks={[landmark]} buildings={[building]} />);
    await waitFor(() => expect(fake.circleMarker).toHaveBeenCalled());
    expect(fake.circleMarker).toHaveBeenCalledWith([1, 2], expect.objectContaining({ fillColor: "var(--primary)" }));
    expect(fake.polyline).not.toHaveBeenCalled();
    const labels = fake.layer.bindTooltip.mock.calls.map(([element]) => element as HTMLElement);
    expect(labels.some(element => element.textContent === "<script>praça</script>" && element.children.length === 0)).toBe(true);
    expect(labels.some(element => element.textContent === "Bloco A (Inativo)")).toBe(true);
  });
});

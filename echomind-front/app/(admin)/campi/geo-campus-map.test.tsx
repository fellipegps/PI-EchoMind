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

const props = { center: { lat: -16.328, lng: -48.953 }, zoom: 17, buildings: [], nodes: [], edges: [], draftPoint: null, focusPoint: null };
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
  it("mantém geometria e texto de barreiras, sem desenhar trecho inativo", async () => {
    const nodes = [{ id: "a", campus_id: "c", lat: 1, lng: 2, label: "A" }, { id: "b", campus_id: "c", lat: 3, lng: 4, label: "B" }];
    const edge = { id: "ab", campus_id: "c", from_node_id: "a", to_node_id: "b", distance_m: null, accessible: false, active: true };
    render(<GeoCampusMap {...props} nodes={nodes} edges={[edge, { ...edge, id: "inactive", active: false }]} />);
    await waitFor(() => expect(fake.polyline).toHaveBeenCalled());
    expect(fake.polyline).toHaveBeenCalledWith([[1, 2], [3, 4]], expect.objectContaining({ dashArray: "6 6", weight: 5 }));
    expect(fake.polyline).toHaveBeenCalledTimes(1);
    expect(fake.layer.bindTooltip.mock.calls.some(([element]) => element.textContent === "Trecho com barreira de acessibilidade")).toBe(true);
  });
});

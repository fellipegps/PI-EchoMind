import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Building, Campus } from "@/lib/geocampus-api";
const calls = vi.hoisted(() => ({ map: vi.fn(), remove: vi.fn(), invalidate: vi.fn() }));
vi.mock("leaflet", () => ({
  map: (container: HTMLElement) => {
    calls.map();
    const map = { container, setView: () => map, on: vi.fn(), remove: calls.remove, invalidateSize: calls.invalidate, fitBounds: vi.fn() };
    return map;
  },
  tileLayer: () => ({ addTo: vi.fn() }),
  layerGroup: () => { const layer = { addTo: () => layer, clearLayers: vi.fn() };return layer; },
  circleMarker: () => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const marker = { addTo: (target: { container?: HTMLElement }) => { target.container?.append(element);return marker; }, getElement: () => element, bindTooltip: vi.fn(), on: vi.fn(), setRadius: vi.fn(), setStyle: vi.fn() };
    return marker;
  },
  circle: () => ({ addTo: vi.fn() }),
  polyline: () => ({ addTo: vi.fn() }),
  latLngBounds: () => { const bounds = { extend: vi.fn(), pad: () => bounds };return bounds; },
}));
import { CampusMapView } from "./campus-map-view";
const campus: Campus = { id: "c", name: "Campus de teste", description: null, center_lat: 0, center_lng: 0, zoom: 17, active: true };
const buildings: Building[] = [{ id: "b", campus_id: "c", name: "Prédio de teste", description: null, category: "ensino", entrance_lat: 0, entrance_lng: 0, entrance_node_id: "n", active: true }];
const nodes: [] = [], edges: [] = [];

describe("Ciclo de vida e acessibilidade do mapa", () => {
  it("preserva uma montagem ao atualizar posições/destino e libera o Leaflet ao desmontar", async () => {
    calls.map.mockClear();calls.remove.mockClear();
    const onSelectBuilding = vi.fn();
    const props = { campus, buildings, nodes, edges, destinationId: null, route: null, fix: null, manualOrigin: null, onSelectBuilding, onSelectManualOrigin: vi.fn() };
    const { rerender, unmount } = render(<CampusMapView {...props} />);
    await screen.findByRole("button", { name: "Selecionar Prédio de teste como destino" });
    expect(calls.map).toHaveBeenCalledOnce();
    const element = screen.getByRole("region", { name: "Mapa geográfico do Campus de teste" });
    rerender(<CampusMapView {...props} destinationId="b" fix={{ lat: 0, lng: 0, accuracy: 12, timestamp: 1 }} />);
    rerender(<CampusMapView {...props} destinationId="b" fix={{ lat: 0.0001, lng: 0, accuracy: 10, timestamp: 2 }} />);
    expect(screen.getByRole("region", { name: "Mapa geográfico do Campus de teste" })).toBe(element);
    expect(calls.map).toHaveBeenCalledOnce();
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
    fireEvent.keyDown(screen.getByRole("button"), { key: "Enter" });
    fireEvent.keyDown(screen.getByRole("button"), { key: " " });
    expect(onSelectBuilding).toHaveBeenNthCalledWith(1, "b");
    expect(onSelectBuilding).toHaveBeenNthCalledWith(2, "b");
    unmount();
    await waitFor(() => expect(calls.remove).toHaveBeenCalledOnce());
  });
});

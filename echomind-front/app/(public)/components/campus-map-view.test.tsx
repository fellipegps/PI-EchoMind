import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Building, Campus, Landmark } from "@/lib/geocampus-api";
const calls = vi.hoisted(() => ({ map: vi.fn(), remove: vi.fn(), invalidate: vi.fn(), polyline: vi.fn() }));
vi.mock("leaflet", () => ({
  map: (container: HTMLElement) => {
    calls.map();
    const map = { container, setView: () => map, remove: calls.remove, invalidateSize: calls.invalidate };
    return map;
  },
  tileLayer: () => ({ addTo: vi.fn() }),
  circleMarker: () => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const marker = { addTo: (target: { container?: HTMLElement }) => { target.container?.append(element); return marker; }, getElement: () => element, bindTooltip: vi.fn(), on: vi.fn() };
    return marker;
  },
  polyline: calls.polyline,
}));
import { CampusMapView } from "./campus-map-view";
const campus: Campus = { id: "c", name: "Campus de teste", description: null, center_lat: 0, center_lng: 0, zoom: 17, active: true };
const buildings: Building[] = [{ id: "b", campus_id: "c", public_code: "code-b", name: "Bloco A", description: null, category: "ensino", entrance_lat: 0, entrance_lng: 0, active: true, photos: [] }];
const landmarks: Landmark[] = [{ id: "l", campus_id: "c", public_code: "code-l", name: "Jardim", description: null, lat: 0, lng: 0.001, active: true, photos: [] }];

describe("Mapa visual e acessibilidade", () => {
  it("abre fichas pelos marcadores com teclado, atualiza callback e libera Leaflet", async () => {
    vi.clearAllMocks();
    const firstOpen = vi.fn(), latestOpen = vi.fn();
    const { rerender, unmount } = render(<CampusMapView campus={campus} buildings={buildings} landmarks={landmarks} onOpenPlace={firstOpen} />);
    const block = await screen.findByRole("link", { name: "Abrir ficha de Bloco A" });
    const landmark = screen.getByRole("link", { name: "Abrir ficha de Jardim" });
    fireEvent.keyDown(block, { key: "Enter" });
    expect(firstOpen).toHaveBeenCalledWith("building", "code-b");
    rerender(<CampusMapView campus={campus} buildings={buildings} landmarks={landmarks} onOpenPlace={latestOpen} />);
    fireEvent.keyDown(landmark, { key: "Enter" });
    expect(latestOpen).toHaveBeenCalledWith("landmark", "code-l");
    expect(calls.map).toHaveBeenCalledOnce();
    expect(calls.polyline).not.toHaveBeenCalled();
    unmount();
    await waitFor(() => expect(calls.remove).toHaveBeenCalledOnce());
  });
});

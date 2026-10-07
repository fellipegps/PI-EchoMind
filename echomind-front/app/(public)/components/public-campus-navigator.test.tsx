import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PublicGeoCampus } from "@/lib/geocampus-api";

const apiMocks = vi.hoisted(() => ({ publicMap: vi.fn() }));

vi.mock("@/lib/geocampus-api", () => ({
  geoCampusApi: { publicMap: apiMocks.publicMap },
}));

vi.mock("./campus-map-view", () => ({
  CampusMapView: ({ onSelectManualOrigin }: { onSelectManualOrigin: (point: { lat: number; lng: number }) => void }) => (
    <button type="button" onClick={() => onSelectManualOrigin({ lat: 0, lng: 0 })}>Marcar origem no mapa</button>
  ),
}));

import { PublicCampusNavigator } from "./public-campus-navigator";

const campusData: PublicGeoCampus = {
  campuses: [{ id: "campus-1", name: "Campus Centro", description: null, center_lat: 0, center_lng: 0, zoom: 17, active: true }],
  buildings: [
    { id: "gate", campus_id: "campus-1", name: "Portaria", description: null, category: "acesso", entrance_lat: 0, entrance_lng: 0, entrance_node_id: "a", active: true },
    { id: "block", campus_id: "campus-1", name: "Bloco A", description: "Ensino e pesquisa", category: "ensino", entrance_lat: 0.0001, entrance_lng: 0.0001, entrance_node_id: "d", active: true },
  ],
  spaces: [{ id: "lab", campus_id: "campus-1", building_id: "block", name: "Laboratório de Química", kind: "laboratório", floor: "1º andar", description: "Ala leste", active: true }],
  nodes: [
    { id: "a", campus_id: "campus-1", lat: 0, lng: 0, label: "Portaria" },
    { id: "b", campus_id: "campus-1", lat: 0, lng: 0.0001, label: "Praça" },
    { id: "c", campus_id: "campus-1", lat: 0.0001, lng: 0, label: "Rampa" },
    { id: "d", campus_id: "campus-1", lat: 0.0001, lng: 0.0001, label: "Bloco A" },
  ],
  edges: [
    { id: "ab", campus_id: "campus-1", from_node_id: "a", to_node_id: "b", distance_m: 10, accessible: false, active: true },
    { id: "bd", campus_id: "campus-1", from_node_id: "b", to_node_id: "d", distance_m: 10, accessible: true, active: true },
    { id: "ac", campus_id: "campus-1", from_node_id: "a", to_node_id: "c", distance_m: 16, accessible: true, active: true },
    { id: "cd", campus_id: "campus-1", from_node_id: "c", to_node_id: "d", distance_m: 16, accessible: true, active: true },
  ],
};

describe("PublicCampusNavigator", () => {
  beforeEach(() => {
    apiMocks.publicMap.mockReset();
    apiMocks.publicMap.mockResolvedValue(campusData);
  });

  it("busca espaços e calcula o caminho acessível a partir de origem manual", async () => {
    const user = userEvent.setup();
    const available = vi.fn();
    render(<PublicCampusNavigator publicSlug="universidade" onAvailabilityChange={available} />);

    expect(await screen.findByText("Encontre o caminho até a entrada")).toBeInTheDocument();
    expect(apiMocks.publicMap).toHaveBeenCalledWith("universidade");
    expect(available).toHaveBeenCalledWith(true);
    await user.selectOptions(screen.getByLabelText("Origem cadastrada"), "gate");
    await user.type(screen.getByLabelText("Buscar prédio ou espaço"), "química");
    await user.click(screen.getByRole("button", { name: /Laboratório de Química · 1º andar/ }));

    expect(screen.getByText(/20 m · cerca de 1 min a pé/)).toBeInTheDocument();
    expect(screen.getByText(/Bloco A · 1º andar · Ala leste/)).toBeInTheDocument();
    await user.click(screen.getByLabelText("Usar apenas caminhos acessíveis"));
    expect(screen.getByText(/32 m · cerca de 1 min a pé/)).toBeInTheDocument();
  });

  it("acompanha a posição somente após interação, mostra precisão e cancela watch", async () => {
    const user = userEvent.setup();
    let success: PositionCallback = () => {};
    let failure: PositionErrorCallback = () => {};
    const watchPosition = vi.fn((onSuccess: PositionCallback, onError: PositionErrorCallback) => {
      success = onSuccess;
      failure = onError;
      return 42;
    });
    const clearWatch = vi.fn();
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { watchPosition, clearWatch },
    });
    const { unmount } = render(<PublicCampusNavigator publicSlug="universidade" />);

    await screen.findByText("Encontre o caminho até a entrada");
    expect(watchPosition).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Usar minha localização" }));
    expect(watchPosition).toHaveBeenCalledOnce();
    act(() => success({ coords: { latitude: 0, longitude: 0, accuracy: 12 }, timestamp: 1 } as GeolocationPosition));
    expect(screen.getByText("Precisão da localização: ±12 m")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Parar acompanhamento" }));
    expect(clearWatch).toHaveBeenCalledWith(42);
    await user.click(screen.getByRole("button", { name: "Usar minha localização" }));
    act(() => failure({ code: 1 } as GeolocationPositionError));
    expect(screen.getByText(/A localização foi negada/)).toBeInTheDocument();
    expect(clearWatch).toHaveBeenCalledTimes(2);
    unmount();
  });

  it("permite marcar a origem no mapa quando não há GPS", async () => {
    const user = userEvent.setup();
    render(<PublicCampusNavigator publicSlug="universidade" />);
    await screen.findByText("Encontre o caminho até a entrada");
    await user.click(screen.getByRole("button", { name: "Marcar origem no mapa" }));
    await user.click(screen.getByRole("button", { name: /Bloco A ensino/ }));
    expect(screen.getByText(/20 m · cerca de 1 min a pé/)).toBeInTheDocument();
  });

  it("mantém o mapa legado quando a instituição ainda não marcou prédios", async () => {
    const available = vi.fn();
    apiMocks.publicMap.mockResolvedValueOnce({ ...campusData, buildings: [] });
    render(<PublicCampusNavigator publicSlug="universidade" onAvailabilityChange={available} />);
    await waitFor(() => expect(available).toHaveBeenCalledWith(false));
    expect(screen.queryByText("Encontre o caminho até a entrada")).not.toBeInTheDocument();
  });
});

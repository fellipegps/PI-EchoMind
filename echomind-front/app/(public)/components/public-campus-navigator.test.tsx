import { act, render, screen } from "@testing-library/react";
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
    render(<PublicCampusNavigator publicSlug="universidade" />);

    expect(await screen.findByText("Encontre o caminho até a entrada")).toBeInTheDocument();
    expect(apiMocks.publicMap).toHaveBeenCalledWith("universidade");
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

  it("informa indisponibilidade quando a instituição ainda não marcou prédios", async () => {
    apiMocks.publicMap.mockResolvedValueOnce({ ...campusData, buildings: [] });
    render(<PublicCampusNavigator publicSlug="universidade" />);
    expect(await screen.findByRole("heading", { name: "Mapa do campus indisponível" })).toBeInTheDocument();
    expect(screen.queryByText("Encontre o caminho até a entrada")).not.toBeInTheDocument();
  });

  it("informa carregamento e trata falha de leitura sem expor o erro interno", async () => {
    let reject!: (error: Error) => void;
    apiMocks.publicMap.mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
    render(<PublicCampusNavigator publicSlug="universidade" />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando mapa do campus…");
    await act(async () => reject(new Error("SEGREDO_INTERNO")));
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar o mapa do campus agora.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("SEGREDO_INTERNO");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("isola campi ativos e limpa origem/destino ao trocar campus", async () => {
    const user = userEvent.setup();
    apiMocks.publicMap.mockResolvedValueOnce({ ...campusData,
      campuses: [...campusData.campuses, { ...campusData.campuses[0], id: "campus-2", name: "Campus Norte" }, { ...campusData.campuses[0], id: "inactive", name: "Campus inativo", active: false }],
      buildings: [...campusData.buildings, { ...campusData.buildings[0], id: "north", campus_id: "campus-2", name: "Biblioteca Norte" }, { ...campusData.buildings[0], id: "inactive", name: "Prédio inativo", active: false }],
    });
    render(<PublicCampusNavigator publicSlug="universidade" />);
    await screen.findByText("Encontre o caminho até a entrada");
    expect(screen.queryByRole("option", { name: "Campus inativo" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Biblioteca Norte/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Prédio inativo/ })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Origem cadastrada"), "gate");
    await user.click(screen.getByRole("button", { name: /Bloco A ensino/ }));
    await user.selectOptions(screen.getByLabelText("Campus", { exact: true }), "campus-2");
    expect(screen.getByRole("button", { name: /Biblioteca Norte/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Bloco A ensino/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/20 m · cerca/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Origem cadastrada")).toHaveValue("");
  });

  it("mostra ausência de percurso sem inventar uma rota substituta", async () => {
    const user = userEvent.setup();
    apiMocks.publicMap.mockResolvedValueOnce({ ...campusData, edges: [] });
    render(<PublicCampusNavigator publicSlug="universidade" />);
    await screen.findByText("Encontre o caminho até a entrada");
    await user.selectOptions(screen.getByLabelText("Origem cadastrada"), "gate");
    await user.click(screen.getByRole("button", { name: /Bloco A ensino/ }));
    expect(screen.getByText(/Não há caminho conectado cadastrado/)).toBeInTheDocument();
    await user.click(screen.getByLabelText("Usar apenas caminhos acessíveis"));
    expect(screen.getByText(/Não há caminho acessível cadastrado/)).toBeInTheDocument();
    expect(screen.queryByText(/min a pé/)).not.toBeInTheDocument();
  });

  it.each([[2, "Não foi possível determinar sua posição"], [3, "A localização demorou a responder"]])("preserva alternativa manual após erro GPS %s", async (code, message) => {
    let failure: PositionErrorCallback = () => {};
    const watchPosition = vi.fn((_success: PositionCallback, error: PositionErrorCallback) => { failure = error; return 90; });
    const clearWatch = vi.fn();
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { watchPosition, clearWatch } });
    const user = userEvent.setup();
    render(<PublicCampusNavigator publicSlug="universidade" />);
    await screen.findByText("Encontre o caminho até a entrada");
    await user.click(screen.getByRole("button", { name: "Usar minha localização" }));
    expect(screen.getByRole("status")).toHaveTextContent("Aguardando localização do aparelho...");
    act(() => failure({ code } as GeolocationPositionError));
    expect(screen.getByRole("status")).toHaveTextContent(message);
    expect(clearWatch).toHaveBeenCalledWith(90);
    await user.selectOptions(screen.getByLabelText("Origem cadastrada"), "gate");
    await user.click(screen.getByRole("button", { name: /Bloco A ensino/ }));
    expect(screen.getByText(/20 m · cerca de 1 min a pé/)).toBeInTheDocument();
  });

  it("filtra sinal impreciso e pequenos saltos; recalcula, chega e libera o observador", async () => {
    let success: PositionCallback = () => {};
    const watchPosition = vi.fn((callback: PositionCallback) => { success = callback; return 71; });
    const clearWatch = vi.fn();
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { watchPosition, clearWatch } });
    const user = userEvent.setup();
    const { unmount } = render(<PublicCampusNavigator publicSlug="universidade" />);
    await screen.findByText("Encontre o caminho até a entrada");
    await user.click(screen.getByRole("button", { name: /Bloco A ensino/ }));
    await user.click(screen.getByRole("button", { name: "Usar minha localização" }));
    const emit = (lat: number, lng: number, accuracy: number, timestamp: number) => act(() => success({ coords: { latitude: lat, longitude: lng, accuracy }, timestamp } as GeolocationPosition));
    emit(0, -0.0002, 90, 1);
    expect(screen.getByRole("status")).toHaveTextContent("Sinal impreciso (±90 m)");
    expect(screen.queryByText(/min a pé/)).not.toBeInTheDocument();
    emit(0, -0.0002, 12, 2);
    const metric = screen.getByText(/min a pé/).textContent;
    emit(0, -0.000199, 12, 3);
    expect(screen.getByText(/min a pé/)).toHaveTextContent(metric!);
    emit(0, 0, 30, 4);
    expect(screen.getByText(/min a pé/)).not.toHaveTextContent(metric!);
    emit(0.0001, 0.0001, 10, 5);
    expect(screen.getByText(/Você chegou à entrada de Bloco A/)).toBeInTheDocument();
    expect(clearWatch).toHaveBeenCalledWith(71);
    expect(watchPosition).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: "Usar minha localização" }));
    unmount();
    expect(watchPosition).toHaveBeenCalledTimes(2);
    expect(clearWatch).toHaveBeenCalledTimes(2);
  });

});

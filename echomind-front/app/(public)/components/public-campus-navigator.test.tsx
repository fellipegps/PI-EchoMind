import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PlaceType, PublicGeoCampus } from "@/lib/geocampus-api";

const mocks = vi.hoisted(() => ({ publicMap: vi.fn(), push: vi.fn() }));
vi.mock("@/lib/api", () => ({ tokenStore: { get: vi.fn(), clear: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/lib/geocampus-api", async (original) => ({
  ...await original<typeof import("@/lib/geocampus-api")>(),
  geoCampusApi: { publicMap: mocks.publicMap },
}));
vi.mock("./campus-map-view", () => ({
  CampusMapView: ({ onOpenPlace }: { onOpenPlace: (type: PlaceType, code: string) => void }) => (
    <button type="button" onClick={() => onOpenPlace("building", "block-code")}>Abrir bloco pelo mapa</button>
  ),
}));
import { PublicCampusNavigator } from "./public-campus-navigator";

const campusData: PublicGeoCampus = {
  campuses: [
    { id: "c1", name: "Campus Centro", description: null, center_lat: 0, center_lng: 0, zoom: 17, active: true },
    { id: "c2", name: "Campus Norte", description: null, center_lat: 1, center_lng: 1, zoom: 17, active: true },
  ],
  buildings: [
    { id: "b1", campus_id: "c1", public_code: "block-code", name: "Bloco A", description: "Ensino e pesquisa", category: "ensino", entrance_lat: 0, entrance_lng: 0, active: true, photos: [] },
    { id: "b2", campus_id: "c2", public_code: "north-code", name: "Bloco Norte", description: null, category: "ensino", entrance_lat: 1, entrance_lng: 1, active: true, photos: [] },
    { id: "hidden", campus_id: "c1", public_code: "hidden-code", name: "Bloco inativo", description: null, category: "ensino", entrance_lat: 0, entrance_lng: 0, active: false, photos: [] },
  ],
  spaces: [
    { id: "lab", campus_id: "c1", public_code: "lab-code", building_id: "b1", name: "Laboratório de Química", kind: "laboratório", floor: "1º andar", description: null, active: true, photos: [] },
    { id: "hidden-lab", campus_id: "c1", public_code: "hidden-lab-code", building_id: "hidden", name: "Sala oculta", kind: "sala", floor: null, description: null, active: true, photos: [] },
  ],
  landmarks: [{ id: "ref", campus_id: "c1", public_code: "ref-code", name: "Praça central", description: "Junto ao jardim", lat: 0, lng: 0, active: true, photos: [] }],
};

describe("Guia visual público", () => {
  beforeEach(() => { vi.clearAllMocks(); mocks.publicMap.mockResolvedValue(campusData); });

  it("abre a mesma ficha estável pelo mapa e pela lista e encontra um espaço interno", async () => {
    const user = userEvent.setup();
    render(<PublicCampusNavigator publicSlug="universidade" />);
    expect(await screen.findByText("Reconheça os locais do campus")).toBeInTheDocument();
    const href = "/p/universidade/locais/building/block-code";
    expect(screen.getByRole("link", { name: "Ver ficha de Bloco A" })).toHaveAttribute("href", href);
    await user.click(screen.getByRole("button", { name: "Abrir bloco pelo mapa" }));
    expect(mocks.push).toHaveBeenCalledWith(href);
    expect(screen.getByRole("link", { name: "Ver ficha de Praça central" })).toHaveAttribute("href", "/p/universidade/locais/landmark/ref-code");
    await user.type(screen.getByLabelText("Buscar bloco, espaço ou referência"), "química");
    expect(screen.getByRole("link", { name: "Laboratório de Química · 1º andar" })).toHaveAttribute("href", "/p/universidade/locais/space/lab-code");
    expect(screen.queryByText("Praça central")).not.toBeInTheDocument();
  });

  it("mantém o guia sem solicitar geolocalização e separa campi e locais publicados", async () => {
    const user = userEvent.setup();
    const watchPosition = vi.fn(), getCurrentPosition = vi.fn();
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { watchPosition, getCurrentPosition } });
    render(<PublicCampusNavigator publicSlug="universidade" />);
    await screen.findByText("Reconheça os locais do campus");
    expect(screen.queryByText("Bloco inativo")).not.toBeInTheDocument();
    expect(screen.queryByText("Sala oculta")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /minha localização|acompanhamento/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/caminhos acessíveis|Origem cadastrada/)).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Campus"), "c2");
    expect(screen.getByRole("link", { name: "Ver ficha de Bloco Norte" })).toBeInTheDocument();
    expect(screen.queryByText("Praça central")).not.toBeInTheDocument();
    expect(watchPosition).not.toHaveBeenCalled();
    expect(getCurrentPosition).not.toHaveBeenCalled();
  });

  it("oferece os pontos de referência mesmo sem blocos e mostra busca vazia", async () => {
    mocks.publicMap.mockResolvedValue({ ...campusData, buildings: [], spaces: [] });
    const user = userEvent.setup();
    render(<PublicCampusNavigator publicSlug="universidade" />);
    expect(await screen.findByRole("link", { name: "Ver ficha de Praça central" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Buscar bloco, espaço ou referência"), "auditório");
    expect(screen.getByRole("status")).toHaveTextContent("Nenhum local encontrado");
  });

  it("mostra indisponibilidade, erro sanitizado e não mantém dados de outra instituição", async () => {
    const { rerender } = render(<PublicCampusNavigator publicSlug="universidade" />);
    await screen.findByText("Bloco A");
    let resolve: (value: PublicGeoCampus) => void = () => {};
    mocks.publicMap.mockImplementationOnce(() => new Promise<PublicGeoCampus>((done) => { resolve = done; }));
    rerender(<PublicCampusNavigator publicSlug="outra" />);
    expect(screen.queryByText("Bloco A")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Carregando");
    await act(async () => resolve({ campuses: [], buildings: [], spaces: [], landmarks: [] }));
    expect(await screen.findByText("Mapa do campus indisponível")).toBeInTheDocument();
    mocks.publicMap.mockRejectedValueOnce(new Error("postgres credencial interna"));
    rerender(<PublicCampusNavigator publicSlug="falha" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar o mapa");
    expect(screen.queryByText(/credencial/)).not.toBeInTheDocument();
  });
});

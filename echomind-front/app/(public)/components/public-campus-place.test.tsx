import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PublicPlace } from "@/lib/geocampus-api";
const apiMocks = vi.hoisted(() => ({ publicPlace: vi.fn() }));
vi.mock("@/lib/api", () => ({ tokenStore: { get: vi.fn(), clear: vi.fn() } }));
vi.mock("@/lib/geocampus-api", async (original) => ({
  ...await original<typeof import("@/lib/geocampus-api")>(),
  geoCampusApi: { publicPlace: apiMocks.publicPlace },
}));
import { PublicCampusPlace } from "./public-campus-place";
const data: PublicPlace = {
  type: "space",
  campus: { id: "c", name: "Campus Centro", description: null, center_lat: 0, center_lng: 0, zoom: 17, active: true },
  place: { id: "s", campus_id: "c", public_code: "s-code", building_id: "b", name: "Auditório Azul", kind: "auditorio", floor: "Térreo", description: "Ao lado da recepção.", active: true,
    photos: [{ id: "two", caption: "Vista interna", sort_order: 2, url: "/public/u/photos/two" }, { id: "one", caption: "Entrada", sort_order: 1, url: "/public/u/photos/one" }] },
  building: { id: "b", campus_id: "c", public_code: "b-code", name: "Bloco A", description: null, category: "ensino", entrance_lat: 0, entrance_lng: 0, active: true, photos: [] },
};

describe("Ficha pública do local", () => {
  beforeEach(() => { vi.clearAllMocks(); apiMocks.publicPlace.mockResolvedValue(data); });
  it("carrega pelo código do QR, apresenta várias fotos em ordem e identifica o bloco", async () => {
    render(<PublicCampusPlace publicSlug="universidade" type="space" publicCode="s-code" />);
    expect(await screen.findByRole("heading", { name: "Auditório Azul" })).toBeInTheDocument();
    expect(apiMocks.publicPlace).toHaveBeenCalledWith("universidade", "space", "s-code");
    expect(screen.getByText("Ao lado da recepção.")).toBeInTheDocument();
    expect(screen.getByText("Andar · Térreo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bloco A" })).toHaveAttribute("href", "/p/universidade/locais/building/b-code");
    expect(screen.getByRole("link", { name: "Voltar aos locais do campus" })).toHaveAttribute("href", "/p/universidade?tab=locais");
    const images = within(screen.getByRole("region", { name: "Fotos de referência" })).getAllByRole("img");
    expect(images.map((image) => image.getAttribute("alt"))).toEqual(["Entrada", "Vista interna"]);
    expect(images[0].getAttribute("src")).toContain("/public/u/photos/one");
    fireEvent.error(images[0]);
    expect(screen.getByRole("status")).toHaveTextContent("Esta foto está indisponível");
    expect(screen.getByAltText("Vista interna")).toBeInTheDocument();
  });

  it("exibe estado sem fotos mantendo nome e descrição", async () => {
    apiMocks.publicPlace.mockResolvedValue({ ...data, place: { ...data.place, photos: [] } });
    render(<PublicCampusPlace publicSlug="universidade" type="space" publicCode="s-code" />);
    expect(await screen.findByText("A instituição ainda não publicou fotos deste local.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Auditório Azul" })).toBeInTheDocument();
  });

  it("permite repetir após código indisponível ou falha de rede sem exibir detalhe interno", async () => {
    apiMocks.publicPlace.mockRejectedValueOnce(new Error("Falha secreta do banco"));
    const user = userEvent.setup();
    render(<PublicCampusPlace publicSlug="universidade" type="space" publicCode="s-code" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível abrir esta ficha");
    expect(screen.queryByText(/secreta/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByRole("heading", { name: "Auditório Azul" })).toBeInTheDocument();
  });

  it("ignora resposta antiga ao trocar instituição ou código", async () => {
    let resolveOld: (value: PublicPlace) => void = () => {};
    apiMocks.publicPlace.mockImplementationOnce(() => new Promise<PublicPlace>((resolve) => { resolveOld = resolve; }));
    const { rerender } = render(<PublicCampusPlace publicSlug="antiga" type="space" publicCode="old-code" />);
    rerender(<PublicCampusPlace publicSlug="nova" type="space" publicCode="s-code" />);
    await screen.findByRole("heading", { name: "Auditório Azul" });
    await act(async () => resolveOld({ ...data, place: { ...data.place, name: "Resposta antiga" } }));
    expect(screen.queryByText("Resposta antiga")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bloco A" })).toHaveAttribute("href", "/p/nova/locais/building/b-code");
  });
});

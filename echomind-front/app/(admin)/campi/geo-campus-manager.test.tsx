import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  campuses: { list: vi.fn(), prepareModel: vi.fn() },
  buildings: { list: vi.fn(), rename: vi.fn() },
  spaces: { list: vi.fn(), update: vi.fn(), create: vi.fn() },
  landmarks: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/geocampus-api", () => ({ geoCampusApi: api, publicPlaceHref: () => "/ficha" }));
vi.mock("@/lib/api", () => ({ configApi: { get: vi.fn().mockResolvedValue({ public_slug: "universidade" }) } }));
vi.mock("./place-media-manager", () => ({ PlaceMediaManager: () => <div>Gerenciador de fotos</div> }));
vi.mock("./place-qr-code", () => ({ PlaceQrCode: ({ publicSlug, publicCode }: { publicSlug: string; publicCode: string }) => <div>{publicSlug}/{publicCode}</div> }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./geo-campus-map", () => ({
  GeoCampusMap: ({ onPickPoint }: { onPickPoint?: (point: { lat: number; lng: number }) => void }) =>
    <button type="button" onClick={() => onPickPoint?.({ lat: -16.3281234, lng: -48.9534567 })}>Marcar ponto no mapa</button>,
}));
vi.mock("../../(public)/components/campus-guide-view", () => ({
  CampusGuideView: ({ onManagePlace }: { onManagePlace: (id: string) => void }) =>
    <button type="button" onClick={() => onManagePlace("building:bloco-a")}>Maquete e satélite</button>,
}));

import { GeoCampusManager } from "./geo-campus-manager";
import { toast } from "sonner";

const campus = { id: "campus-1", name: "Campus Central", description: null, center_lat: -16.328, center_lng: -48.953, zoom: 17, active: true };
const landmark = { id: "ref-1", campus_id: campus.id, name: "Praça central", description: null,
  lat: -16.3281234, lng: -48.9534567, active: true, photos: [], public_code: "public-praca" };

beforeEach(() => {
  vi.clearAllMocks();
  for (const group of Object.values(api)) {
    for (const mock of Object.values(group)) mock.mockReset();
  }
  api.campuses.list.mockResolvedValue([campus]);
  api.buildings.list.mockResolvedValue([]);
  api.spaces.list.mockResolvedValue([]);
  api.landmarks.list.mockResolvedValue([landmark]);
});

describe("Gestão de referências do campus", () => {
  it("prepara a maquete e abre a edição do bloco selecionado, com suas fotos e locais internos", async () => {
    const user = userEvent.setup();
    const block = { id: "bloco-a", campus_id: campus.id, name: "Bloco A", category: "bloco", model_destination_id: "bloco-a",
      public_code: "bloco-a", photos: [], active: true, entrance_lng: 0, entrance_lat: 0, description: null };
    const space = { id: "lab", campus_id: campus.id, building_id: block.id, public_code: "lab", name: "Laboratório",
      kind: "laboratório", floor: "Piso 1", description: "Descrição anterior", active: true, photos: [] };
    api.campuses.list.mockResolvedValue([{ ...campus, model_key: "anapolis" }]);
    api.campuses.prepareModel.mockResolvedValue(undefined);
    api.buildings.list.mockResolvedValueOnce([block]).mockResolvedValue([{ ...block, name: "Bloco de Saúde" }]);
    api.spaces.list.mockResolvedValue([space]);
    api.buildings.rename.mockResolvedValue(undefined);
    api.spaces.update.mockResolvedValue(undefined);
    render(<GeoCampusManager />);
    await user.click(await screen.findByRole("button", { name: "Maquete e satélite" }));
    expect(api.campuses.prepareModel).toHaveBeenCalledWith(campus.id);
    expect(screen.getByText("Gerenciador de fotos")).toBeVisible();
    const name = screen.getByLabelText("Nome do bloco");
    await user.clear(name);
    await user.type(name, "Bloco de Saúde");
    await user.click(screen.getByRole("button", { name: "Salvar nome do bloco" }));
    expect(api.buildings.rename).toHaveBeenCalledWith(campus.id, block.id, "Bloco de Saúde");
    await user.click(screen.getByRole("button", { name: "Editar Laboratório" }));
    const description = screen.getByLabelText("Descrição do local interno");
    await user.clear(description);
    await user.type(description, "Descrição atualizada");
    await user.click(screen.getByRole("button", { name: "Salvar local interno" }));
    expect(api.spaces.update).toHaveBeenCalledWith(campus.id, space.id, expect.objectContaining({ description: "Descrição atualizada" }));
  });
  it("permite cadastrar apenas pontos e abre fotos e QR Code após salvar", async () => {
    const user = userEvent.setup();
    const garden = { ...landmark, id: "ref-2", name: "Jardim", public_code: "public-jardim" };
    api.landmarks.create.mockResolvedValue(garden);
    api.landmarks.list.mockResolvedValueOnce([landmark]).mockResolvedValue([landmark, garden]);
    render(<GeoCampusManager />);
    expect(screen.getByRole("link", { name: "Falar com a equipe EchoMind" })).toHaveAttribute("href", "/privacidade#contato-equipe");
    expect(screen.queryByRole("button", { name: /novo campus|novo prédio|novo espaço/i })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Novo ponto" }));
    await user.type(screen.getByLabelText("Nome"), "Jardim");
    await user.click(screen.getByRole("button", { name: "Marcar ponto no mapa" }));
    await user.click(screen.getByRole("button", { name: "Salvar ponto" }));
    await waitFor(() => expect(api.landmarks.create).toHaveBeenCalledWith(campus.id, {
      name: "Jardim", description: null, lat: landmark.lat, lng: landmark.lng, active: true,
    }));
    expect(await screen.findByText("universidade/public-jardim")).toBeInTheDocument();
    expect(screen.getByText("Gerenciador de fotos")).toBeInTheDocument();
  });

  it("orienta o contato com a equipe quando o portal ainda não tem campus publicado", async () => {
    api.campuses.list.mockResolvedValue([]);
    render(<GeoCampusManager />);
    expect(await screen.findByText(/Nenhum campus publicado/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Novo ponto" })).not.toBeInTheDocument();
    expect(api.landmarks.list).not.toHaveBeenCalled();
  });

  it("preserva o formulário após erro e permite ocultar um ponto", async () => {
    const user = userEvent.setup();
    api.landmarks.update.mockRejectedValueOnce(new Error("Falha sintética"));
    api.landmarks.update.mockResolvedValueOnce({ ...landmark, active: false });
    api.landmarks.list.mockResolvedValueOnce([landmark]).mockResolvedValue([{ ...landmark, active: false }]);
    render(<GeoCampusManager />);
    await user.click(await screen.findByRole("button", { name: "Editar Praça central" }));
    await user.click(screen.getByRole("checkbox", { name: "Visível no mapa público" }));
    await user.click(screen.getByRole("button", { name: "Salvar ponto" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha sintética"));
    expect(screen.getByLabelText("Latitude")).toHaveValue(landmark.lat);
    await user.click(screen.getByRole("button", { name: "Salvar ponto" }));
    expect(await screen.findByText("Oculto")).toBeInTheDocument();
    expect(api.landmarks.update).toHaveBeenLastCalledWith(campus.id, landmark.id, expect.objectContaining({ active: false }));
  });

  it("ignora resposta atrasada de outro campus", async () => {
    let resolveOld!: (value: typeof landmark[]) => void;
    const pending = new Promise<typeof landmark[]>((resolve) => { resolveOld = resolve; });
    const north = { ...landmark, id: "north-1", campus_id: "campus-2", name: "Jardim Norte" };
    api.campuses.list.mockResolvedValue([campus, { ...campus, id: north.campus_id, name: "Campus Norte" }]);
    api.landmarks.list.mockImplementation((id: string) => id === campus.id ? pending : Promise.resolve([north]));
    const user = userEvent.setup();
    render(<GeoCampusManager />);
    await user.selectOptions(await screen.findByLabelText("Campus"), north.campus_id);
    expect(await screen.findByText(north.name)).toBeInTheDocument();
    await act(async () => resolveOld([landmark]));
    expect(screen.queryByText(landmark.name)).not.toBeInTheDocument();
  });

  it("pede confirmação antes de excluir o ponto", async () => {
    const user = userEvent.setup();
    api.landmarks.delete.mockResolvedValue(undefined);
    api.landmarks.list.mockResolvedValueOnce([landmark]).mockResolvedValue([]);
    render(<GeoCampusManager />);
    const trigger = await screen.findByRole("button", { name: "Excluir Praça central" });
    await user.click(trigger);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancelar" }));
    expect(api.landmarks.delete).not.toHaveBeenCalled();
    await user.click(trigger);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Excluir" }));
    await waitFor(() => expect(api.landmarks.delete).toHaveBeenCalledWith(campus.id, landmark.id));
    expect(screen.queryByText("Praça central")).not.toBeInTheDocument();
  });
});

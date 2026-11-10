import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  campuses: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  buildings: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  spaces: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  landmarks: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/lib/geocampus-api", () => ({ geoCampusApi: api }));
vi.mock("@/lib/api", () => ({ configApi: { get: vi.fn().mockResolvedValue({ public_slug: "universidade" }) } }));
vi.mock("./place-media-manager", () => ({ PlaceMediaManager: () => <div>Gerenciador de fotos</div> }));
vi.mock("./place-qr-code", () => ({ PlaceQrCode: ({ publicSlug, publicCode }: { publicSlug: string; publicCode: string }) => <div>{publicSlug}/{publicCode}</div> }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./geo-campus-map", () => ({
  GeoCampusMap: ({ onPickPoint }: { onPickPoint?: (point: { lat: number; lng: number }) => void }) =>
    <button type="button" onClick={() => onPickPoint?.({ lat: -16.3281234, lng: -48.9534567 })}>Marcar ponto no mapa</button>,
}));

import { GeoCampusManager } from "./geo-campus-manager";
import { toast } from "sonner";

const campus = {
  id: "campus-1",
  name: "Campus Central",
  description: null,
  center_lat: -16.328,
  center_lng: -48.953,
  zoom: 17,
  active: true,
};
const building = {
  id: "building-1",
  campus_id: campus.id,
  name: "Bloco A",
  description: null,
  category: "prédio",
  entrance_lat: -16.328,
  entrance_lng: -48.953,
  public_code: "public-bloco-a",
  photos: [],
  active: true,
};
describe("GeoCampusManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    for (const group of Object.values(api)) {
      for (const mock of Object.values(group)) mock.mockReset();
    }
    api.campuses.list.mockResolvedValue([campus]);
    api.buildings.list.mockResolvedValue([building]);
    api.spaces.list.mockResolvedValue([]);
    api.landmarks.list.mockResolvedValue([]);
  });

  it("marca o bloco no mapa sem vínculos com rotas nem tenant_id", async () => {
    const user = userEvent.setup();
    api.buildings.create.mockResolvedValue({ ...building, id: "building-2", name: "Bloco B" });
    render(<GeoCampusManager />);

    expect(await screen.findByText("Bloco A")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Novo prédio" }));
    await user.type(screen.getByLabelText("Nome"), "Bloco B");
    await user.click(screen.getByRole("button", { name: "Marcar ponto no mapa" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(api.buildings.create).toHaveBeenCalledWith("campus-1", {
      name: "Bloco B",
      description: null,
      category: "prédio",
      entrance_lat: -16.3281234,
      entrance_lng: -48.9534567,
      active: true,
    }));
    expect(api.buildings.create.mock.calls[0][1]).not.toHaveProperty("tenant_id");
  });

  it("cadastra espaços internos vinculados ao prédio", async () => {
    const user = userEvent.setup();
    api.spaces.create.mockResolvedValue({ id: "space-1", campus_id: campus.id, building_id: building.id, name: "Auditório 1", kind: "auditório", floor: "2º andar", description: null, active: true });
    render(<GeoCampusManager />);

    await screen.findByText("Bloco A");
    await user.click(screen.getByRole("tab", { name: "Espaços internos" }));
    await user.click(screen.getByRole("button", { name: "Novo espaço" }));
    await user.type(screen.getByLabelText("Nome"), "Auditório 1");
    await user.type(screen.getByLabelText("Piso"), "2º andar");
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(api.spaces.create).toHaveBeenCalledWith("campus-1", {
      building_id: "building-1",
      name: "Auditório 1",
      kind: "auditório",
      floor: "2º andar",
      description: null,
      active: true,
    }));
  });

  it("cadastra um ponto de referência marcado no mapa", async () => {
    const user = userEvent.setup();
    api.landmarks.create.mockResolvedValue({ id: "ref-1", name: "Praça central", photos: [] });
    render(<GeoCampusManager />);
    await screen.findByText("Bloco A");
    await user.click(screen.getByRole("tab", { name: "Pontos de referência" }));
    await user.click(screen.getByRole("button", { name: "Novo ponto de referência" }));
    await user.type(screen.getByLabelText("Nome"), "Praça central");
    await user.click(screen.getByRole("button", { name: "Marcar ponto no mapa" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(api.landmarks.create).toHaveBeenCalledWith("campus-1", {
      name: "Praça central", description: null, lat: -16.3281234, lng: -48.9534567, active: true,
    }));
  });

  it("pede confirmação antes de excluir um prédio", async () => {
    const user = userEvent.setup();
    api.buildings.delete.mockResolvedValue(undefined);
    render(<GeoCampusManager />);

    await screen.findByText("Bloco A");
    await user.click(screen.getByRole("button", { name: "Excluir Bloco A" }));
    expect(api.buildings.delete).not.toHaveBeenCalled();
    const dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Excluir" }));
    await waitFor(() => expect(api.buildings.delete).toHaveBeenCalledWith("campus-1", "building-1"));
  });

  it("descarta resposta atrasada e limpa o editor ao trocar campus", async () => {
    let resolveOld!: (value: typeof building[]) => void;
    const old = new Promise<typeof building[]>((resolve) => { resolveOld = resolve; });
    api.campuses.list.mockResolvedValue([campus, { ...campus, id: "campus-2", name: "Campus Norte" }]);
    api.buildings.list.mockImplementation((id: string) => id === campus.id ? old : Promise.resolve([{ ...building, id: "north", campus_id: "campus-2", name: "Bloco Norte" }]));
    const user = userEvent.setup();
    render(<GeoCampusManager />);
    await screen.findByRole("button", { name: "Editar campus" });
    await user.click(screen.getByRole("button", { name: "Editar campus" }));
    await user.selectOptions(screen.getByLabelText("Campus"), "campus-2");
    expect(screen.queryByLabelText("Nome")).not.toBeInTheDocument();
    await screen.findByText("Bloco Norte");
    await act(async () => resolveOld([building]));
    expect(screen.queryByText("Bloco A")).not.toBeInTheDocument();
    expect(screen.getByText("Bloco Norte")).toBeInTheDocument();
  });

  it("preserva precisão manual e campos ao editar prédio; falha mantém o formulário", async () => {
    const user = userEvent.setup();
    api.buildings.update.mockRejectedValueOnce(new Error("Falha sintética"));
    api.buildings.update.mockResolvedValueOnce(building);
    render(<GeoCampusManager />);
    await user.click(await screen.findByRole("button", { name: "Editar Bloco A" }));
    await user.clear(screen.getByLabelText("Latitude"));
    await user.type(screen.getByLabelText("Latitude"), "-16.123456789");
    await user.clear(screen.getByLabelText("Longitude"));
    await user.type(screen.getByLabelText("Longitude"), "-48.987654321");
    await user.type(screen.getByLabelText("Descrição (opcional)"), "Descrição preservada");
    await user.click(screen.getByRole("checkbox", { name: "Ativo para visitantes" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha sintética"));
    expect(screen.getByLabelText("Latitude")).toHaveValue(-16.123456789);
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(api.buildings.update).toHaveBeenLastCalledWith(campus.id, building.id, {
      name: "Bloco A", description: "Descrição preservada", category: "prédio", entrance_lat: -16.123456789,
      entrance_lng: -48.987654321, active: false,
    }));
    await waitFor(() => expect(screen.queryByLabelText("Latitude")).not.toBeInTheDocument());
  });

  it("bloqueia coordenadas fora da faixa e zoom fracionário", async () => {
    const user = userEvent.setup(); render(<GeoCampusManager />);
    await screen.findByText("Bloco A");
    await user.click(screen.getByRole("button", { name: "Novo campus" }));
    await user.type(screen.getByLabelText("Nome"), "Campus inválido");
    await user.type(screen.getByLabelText("Latitude"), "91");
    await user.type(screen.getByLabelText("Longitude"), "0");
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(api.campuses.create).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText("Latitude")); await user.type(screen.getByLabelText("Latitude"), "0");
    await user.clear(screen.getByLabelText("Zoom inicial do mapa (1 a 19)")); await user.type(screen.getByLabelText("Zoom inicial do mapa (1 a 19)"), "2.5");
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(toast.error).toHaveBeenCalledWith("Informe um zoom de 1 a 19.");
    expect(api.campuses.create).not.toHaveBeenCalled();
  });

  it("oferece guia visual, fotos e QR sem solicitar a localização do administrador", async () => {
    const getCurrentPosition = vi.fn();
    const watchPosition = vi.fn();
    const descriptor = Object.getOwnPropertyDescriptor(navigator, "geolocation");
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition, watchPosition } });
    try {
      const user = userEvent.setup();
      render(<GeoCampusManager />);
      await screen.findByText("Bloco A");
      expect(screen.queryByRole("tab", { name: "Trechos" })).not.toBeInTheDocument();
      expect(screen.queryByRole("tab", { name: "Pontos do caminho" })).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Fotos e QR Code de Bloco A" }));
      expect(screen.getByText("Gerenciador de fotos")).toBeInTheDocument();
      expect(await screen.findByText("universidade/public-bloco-a")).toBeInTheDocument();
      expect(getCurrentPosition).not.toHaveBeenCalled();
      expect(watchPosition).not.toHaveBeenCalled();
    } finally {
      if (descriptor) Object.defineProperty(navigator, "geolocation", descriptor);
      else Reflect.deleteProperty(navigator, "geolocation");
    }
  });

  it("cancelar exclusão não chama API e vínculo impeditivo preserva entidade", async () => {
    const user = userEvent.setup(); api.buildings.delete.mockRejectedValue(new Error("Prédio possui espaços vinculados."));
    render(<GeoCampusManager />);
    const trigger = await screen.findByRole("button", { name: "Excluir Bloco A" });
    await user.click(trigger); await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancelar" }));
    expect(api.buildings.delete).not.toHaveBeenCalled(); expect(trigger).toHaveFocus();
    await user.click(trigger); await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Excluir" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Prédio possui espaços vinculados."));
    expect(screen.getByText("Bloco A")).toBeInTheDocument(); expect(toast.success).not.toHaveBeenCalled();
  });

  it("abas operam com setas e editor devolve foco ao cancelar", async () => {
    const user = userEvent.setup(); render(<GeoCampusManager />); await screen.findByText("Bloco A");
    screen.getByRole("tab", { name: "Prédios e blocos" }).focus(); await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Espaços internos" })).toHaveAttribute("aria-selected", "true");
    const trigger = screen.getByRole("button", { name: "Novo espaço" });
    await user.click(trigger); expect(screen.getByRole("heading", { name: "Cadastrar espaço interno" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Cancelar" })); expect(trigger).toHaveFocus();
  });
});

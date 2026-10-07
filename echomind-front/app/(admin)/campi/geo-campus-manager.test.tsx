import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  campuses: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  buildings: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  spaces: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  nodes: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  edges: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/lib/geocampus-api", () => ({ geoCampusApi: api }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./geo-campus-map", () => ({
  GeoCampusMap: ({ onPickPoint }: { onPickPoint?: (point: { lat: number; lng: number }) => void }) =>
    <button type="button" onClick={() => onPickPoint?.({ lat: -16.3281234, lng: -48.9534567 })}>Marcar ponto no mapa</button>,
}));

import { GeoCampusManager } from "./geo-campus-manager";

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
  entrance_node_id: null,
  active: true,
};
const nodeA = { id: "node-1", campus_id: campus.id, lat: -16.328, lng: -48.953, label: "Portão" };
const nodeB = { id: "node-2", campus_id: campus.id, lat: -16.329, lng: -48.954, label: "Biblioteca" };

describe("GeoCampusManager", () => {
  beforeEach(() => {
    for (const group of Object.values(api)) {
      for (const mock of Object.values(group)) mock.mockReset();
    }
    api.campuses.list.mockResolvedValue([campus]);
    api.buildings.list.mockResolvedValue([building]);
    api.spaces.list.mockResolvedValue([]);
    api.nodes.list.mockResolvedValue([nodeA, nodeB]);
    api.edges.list.mockResolvedValue([]);
  });

  it("marca a entrada no mapa e liga o prédio a um ponto sem enviar tenant_id", async () => {
    const user = userEvent.setup();
    api.buildings.create.mockResolvedValue({ ...building, id: "building-2", name: "Bloco B" });
    render(<GeoCampusManager />);

    expect(await screen.findByText("Bloco A")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Novo prédio" }));
    await user.type(screen.getByLabelText("Nome"), "Bloco B");
    await user.click(screen.getByRole("button", { name: "Marcar ponto no mapa" }));
    await user.selectOptions(screen.getByLabelText("Ponto do caminho na entrada"), "node-1");
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(api.buildings.create).toHaveBeenCalledWith("campus-1", {
      name: "Bloco B",
      description: null,
      category: "prédio",
      entrance_lat: -16.3281234,
      entrance_lng: -48.9534567,
      entrance_node_id: "node-1",
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

  it("cadastra trecho não acessível entre pontos distintos", async () => {
    const user = userEvent.setup();
    api.edges.create.mockResolvedValue({ id: "edge-1", campus_id: campus.id, from_node_id: nodeA.id, to_node_id: nodeB.id, distance_m: 120, accessible: false, active: true });
    render(<GeoCampusManager />);

    await screen.findByText("Bloco A");
    await user.click(screen.getByRole("tab", { name: "Trechos" }));
    await user.click(screen.getByRole("button", { name: "Novo trecho" }));
    await user.type(screen.getByLabelText("Comprimento real em metros (opcional)"), "120");
    await user.click(screen.getByRole("checkbox", { name: "Trecho acessível (sem escadas ou barreiras)" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(api.edges.create).toHaveBeenCalledWith("campus-1", {
      from_node_id: "node-1",
      to_node_id: "node-2",
      distance_m: 120,
      accessible: false,
      active: true,
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
});

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  locationApi: apiMocks,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { CampusLocationsManager } from "./campus-locations-manager";

const location = {
  id: "location-1",
  name: "Biblioteca Central",
  description: "Acervo e salas de estudo.",
  category: "estudo",
  floor: "Térreo",
  building: "Bloco B",
  x: 30,
  y: 40,
  active: true,
  created_at: "2026-09-18T10:00:00Z",
  updated_at: "2026-09-18T10:00:00Z",
};

describe("CampusLocationsManager", () => {
  beforeEach(() => {
    apiMocks.list.mockReset();
    apiMocks.create.mockReset();
    apiMocks.update.mockReset();
    apiMocks.delete.mockReset();
    apiMocks.list.mockResolvedValue([location]);
  });

  it("lista, pesquisa e cadastra um local sem aceitar tenant informado pelo cliente", async () => {
    const user = userEvent.setup();
    apiMocks.create.mockResolvedValue({
      ...location,
      id: "location-2",
      name: "Laboratório de Redes",
      category: "laboratório",
      building: "Bloco F",
      floor: "2º andar",
      x: 61,
      y: 27,
    });

    render(<CampusLocationsManager />);

    expect(await screen.findByText("Biblioteca Central")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Pesquisar locais"), "inexistente");
    expect(screen.getByText("Nenhum local encontrado.")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Pesquisar locais"));

    await user.click(screen.getByRole("button", { name: "Novo local" }));
    const dialog = screen.getByRole("dialog", { name: "Novo local" });
    await user.type(within(dialog).getByLabelText("Nome"), "  Laboratório de Redes  ");
    await user.clear(within(dialog).getByLabelText("Categoria"));
    await user.type(within(dialog).getByLabelText("Categoria"), "laboratório");
    await user.type(within(dialog).getByLabelText("Bloco"), "Bloco F");
    await user.type(within(dialog).getByLabelText("Piso"), "2º andar");
    await user.clear(within(dialog).getByLabelText("Posição X"));
    await user.type(within(dialog).getByLabelText("Posição X"), "61");
    await user.clear(within(dialog).getByLabelText("Posição Y"));
    await user.type(within(dialog).getByLabelText("Posição Y"), "27");
    await user.type(
      within(dialog).getByLabelText("Descrição"),
      "Laboratório para aulas práticas."
    );
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));

    await waitFor(() =>
      expect(apiMocks.create).toHaveBeenCalledWith({
        name: "Laboratório de Redes",
        description: "Laboratório para aulas práticas.",
        category: "laboratório",
        building: "Bloco F",
        floor: "2º andar",
        x: 61,
        y: 27,
        active: true,
      })
    );
    expect(apiMocks.create.mock.calls[0][0]).not.toHaveProperty("tenant_id");
    expect(await screen.findByText("Laboratório de Redes")).toBeInTheDocument();
  });

  it("exclui o local selecionado e o remove da lista", async () => {
    const user = userEvent.setup();
    apiMocks.delete.mockResolvedValue(undefined);
    render(<CampusLocationsManager />);

    expect(await screen.findByText("Biblioteca Central")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Excluir Biblioteca Central" })
    );
    await user.click(screen.getByRole("button", { name: /^Excluir$/ }));

    await waitFor(() => expect(apiMocks.delete).toHaveBeenCalledWith("location-1"));
    expect(screen.queryByText("Biblioteca Central")).not.toBeInTheDocument();
  });

  it("trata falha de carregamento sem exibir detalhes internos", async () => {
    apiMocks.list.mockRejectedValueOnce(new Error("segredo interno do banco"));
    render(<CampusLocationsManager />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Não foi possível carregar os locais. Tente novamente."
    );
    expect(alert).not.toHaveTextContent("segredo interno do banco");
  });
});

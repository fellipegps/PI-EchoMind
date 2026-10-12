import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
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
    vi.mocked(toast.error).mockClear();
    apiMocks.list.mockReset();
    apiMocks.create.mockReset();
    apiMocks.update.mockReset();
    apiMocks.delete.mockReset();
    apiMocks.list.mockResolvedValue([location]);
  });

  it("pesquisa nome, categoria, bloco e piso sem diferença de caixa", async () => {
    const user = userEvent.setup();
    apiMocks.list.mockResolvedValue([location, { ...location, id: "other", name: "Cantina", category: "alimentação", building: "Bloco A", floor: "Superior" }]);
    render(<CampusLocationsManager />);
    await screen.findByText(location.name);
    const search = screen.getByLabelText("Pesquisar locais");
    for (const term of ["BIBLIOTECA", "ESTUDO", "BLOCO B", "TÉRREO"]) {
      await user.clear(search);
      await user.type(search, term);
      expect(screen.getByText(location.name)).toBeInTheDocument();
      expect(screen.queryByText("Cantina")).not.toBeInTheDocument();
    }
    await user.clear(search);
    await user.type(search, "ausente");
    expect(screen.getByText("Nenhum local encontrado.")).toBeInTheDocument();
  });

  it("edita somente nome preservando coordenadas fracionárias e valores opcionais", async () => {
    const user = userEvent.setup();
    const fractional = { ...location, x: 30.7, y: 40.3, active: false };
    apiMocks.list.mockResolvedValue([fractional]);
    apiMocks.update.mockResolvedValue({ ...fractional, name: "Biblioteca revisada" });
    render(<CampusLocationsManager />);
    await user.click(await screen.findByRole("button", { name: `Editar ${location.name}` }));
    const dialog = screen.getByRole("dialog", { name: "Editar local" });
    expect(within(dialog).getByLabelText("Posição X")).toHaveValue(30.7);
    expect(within(dialog).getByRole("switch", { name: "Exibir no portal" })).not.toBeChecked();
    await user.clear(within(dialog).getByLabelText("Nome"));
    await user.type(within(dialog).getByLabelText("Nome"), "  Biblioteca revisada  ");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(apiMocks.update).toHaveBeenCalledExactlyOnceWith(location.id, { name: "Biblioteca revisada", description: location.description, category: location.category, floor: location.floor, building: location.building, x: 30.7, y: 40.3, active: false }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("bloqueia obrigatórios e normaliza opcionais sem exigir cadastro geográfico", async () => {
    const user = userEvent.setup();
    apiMocks.create.mockResolvedValue({ ...location, id: "new", name: "Local novo", active: false });
    render(<CampusLocationsManager />);
    await screen.findByText(location.name);
    await user.click(screen.getByRole("button", { name: "Novo local" }));
    const dialog = screen.getByRole("dialog", { name: "Novo local" });
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));
    expect(apiMocks.create).not.toHaveBeenCalled();
    await user.type(within(dialog).getByLabelText("Nome"), " Local novo ");
    await user.clear(within(dialog).getByLabelText("Categoria"));
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));
    expect(apiMocks.create).not.toHaveBeenCalled();
    await user.type(within(dialog).getByLabelText("Categoria"), " estudo ");
    await user.type(within(dialog).getByLabelText("Descrição"), "   ");
    await user.click(within(dialog).getByRole("switch", { name: "Exibir no portal" }));
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(apiMocks.create).toHaveBeenCalledExactlyOnceWith({ name: "Local novo", category: "estudo", description: null, floor: null, building: null, x: 50, y: 50, active: false }));
  });

  it("mantém formulário durante envio e após falha, fechando somente no sucesso", async () => {
    const user = userEvent.setup();
    let reject!: (error: Error) => void;
    apiMocks.create.mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
    render(<CampusLocationsManager />);
    await screen.findByText(location.name);
    await user.click(screen.getByRole("button", { name: "Novo local" }));
    const dialog = screen.getByRole("dialog", { name: "Novo local" });
    await user.type(within(dialog).getByLabelText("Nome"), "Nome conservado");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));
    expect(within(dialog).getByRole("button", { name: "Salvando..." })).toBeDisabled();
    expect(dialog).toBeInTheDocument();
    reject(new Error("Não foi possível concluir a solicitação."));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Não foi possível concluir a solicitação."));
    expect(within(dialog).getByLabelText("Nome")).toHaveValue("Nome conservado");
    apiMocks.create.mockResolvedValue({ ...location, id: "created", name: "Nome conservado" });
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("cancela exclusão sem chamada, conserva item na falha e remove após sucesso", async () => {
    const user = userEvent.setup();
    apiMocks.delete.mockRejectedValueOnce(new Error("Falha segura"));
    render(<CampusLocationsManager />);
    const trigger = await screen.findByRole("button", { name: `Excluir ${location.name}` });
    await user.click(trigger);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancelar" }));
    expect(apiMocks.delete).not.toHaveBeenCalled();
    await waitFor(() => expect(trigger).toHaveFocus());
    await user.click(trigger);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Excluir" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha segura"));
    expect(screen.getByText(location.name)).toBeInTheDocument();
    let finish!: () => void;
    apiMocks.delete.mockReturnValueOnce(new Promise<void>((resolve) => { finish = resolve; }));
    await user.click(trigger);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Excluir" }));
    expect(screen.getByText(location.name)).toBeInTheDocument();
    finish();
    await waitFor(() => expect(screen.queryByText(location.name)).not.toBeInTheDocument());
  });

  it("repete leitura após erro seguro e fecha formulário por Escape devolvendo foco", async () => {
    const user = userEvent.setup();
    apiMocks.list.mockRejectedValueOnce(new Error("SEGREDO_INTERNO"));
    render(<CampusLocationsManager />);
    expect(await screen.findByRole("alert")).not.toHaveTextContent("SEGREDO_INTERNO");
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await screen.findByText(location.name);
    expect(apiMocks.list).toHaveBeenCalledTimes(2);
    const trigger = screen.getByRole("button", { name: "Novo local" });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(apiMocks.create).not.toHaveBeenCalled();
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

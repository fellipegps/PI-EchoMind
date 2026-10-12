import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  listCourses: vi.fn(),
  createCourse: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  eventApi: {
    list: mocks.list,
    listCourses: mocks.listCourses,
    createCourse: mocks.createCourse,
    create: mocks.create,
    update: mocks.update,
    delete: mocks.remove,
  },
}));

vi.mock("sonner", () => ({
  toast: { error: mocks.toastError, success: vi.fn() },
}));

vi.mock("@/components/ui/calendar", () => ({
  Calendar: ({ onSelect }: { onSelect: (range: { from: Date; to?: Date }) => void }) => (
    <div>
      <button type="button" onClick={() => onSelect({ from: new Date(2099, 7, 15), to: new Date(2099, 7, 17) })}>
        Selecionar intervalo de teste
      </button>
      <button type="button" onClick={() => onSelect({ from: new Date(2099, 7, 15) })}>
        Selecionar um dia
      </button>
    </div>
  ),
}));

import { EventsManager } from "./events-manager";

const createdEvent = {
  id: "event-1",
  title: "Semana Acadêmica",
  event_date: "2099-08-15",
  event_end_date: "2099-08-17",
  event_type: "outro",
  course: "Geral",
  description: null,
  location: "Auditório Central",
  image_url: "https://cdn.example.com/capa.webp",
  link_url: "https://example.com/inscricoes",
  created_at: "2099-01-01T10:00:00Z",
};

function fillRequiredForm() {
  fireEvent.click(screen.getByRole("button", { name: /Novo evento/i }));
  fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Semana Acadêmica" } });
  fireEvent.change(screen.getByLabelText("Local"), { target: { value: "Auditório Central" } });
  fireEvent.click(screen.getByRole("button", { name: /Selecione o período/i }));
  fireEvent.click(screen.getByRole("button", { name: "Selecionar intervalo de teste" }));
}

describe("EventsManager", () => {
  beforeEach(() => {
    mocks.list.mockReset().mockResolvedValue([]);
    mocks.listCourses.mockReset().mockResolvedValue([{ id: "course-general", name: "Geral" }]);
    mocks.createCourse.mockReset().mockResolvedValue({ id: "course-medicine", name: "Medicina" });
    mocks.create.mockReset().mockResolvedValue(createdEvent);
    mocks.update.mockReset();
    mocks.remove.mockReset();
    mocks.toastError.mockReset();
  });

  it("não exibe publicação e salva o período e as novas URLs em uma única chamada", async () => {
    render(<EventsManager />);
    await screen.findByText("Nenhum evento encontrado.");
    fillRequiredForm();

    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("URL da imagem de capa"), {
      target: { value: createdEvent.image_url },
    });
    fireEvent.change(screen.getByLabelText("Link relacionado"), {
      target: { value: createdEvent.link_url },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce());
    expect(mocks.create).toHaveBeenCalledWith({
      title: "Semana Acadêmica",
      event_date: "2099-08-15",
      event_end_date: "2099-08-17",
      event_type: "outro",
      course: "Geral",
      description: null,
      location: "Auditório Central",
      image_url: createdEvent.image_url,
      link_url: createdEvent.link_url,
    });
  });

  it("usa a mesma data no início e no fim quando só um dia é selecionado", async () => {
    render(<EventsManager />);
    await screen.findByText("Nenhum evento encontrado.");
    fireEvent.click(screen.getByRole("button", { name: /Novo evento/i }));
    fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Evento de um dia" } });
    fireEvent.change(screen.getByLabelText("Local"), { target: { value: "Campus" } });
    fireEvent.click(screen.getByRole("button", { name: /Selecione o período/i }));
    fireEvent.click(screen.getByRole("button", { name: "Selecionar um dia" }));
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce());
    expect(mocks.create.mock.calls[0][0]).toMatchObject({
      event_date: "2099-08-15",
      event_end_date: "2099-08-15",
    });
  });

  it("rejeita URL de imagem sem https e link relacionado inválido", async () => {
    render(<EventsManager />);
    await screen.findByText("Nenhum evento encontrado.");
    fillRequiredForm();
    fireEvent.change(screen.getByLabelText("URL da imagem de capa"), {
      target: { value: "http://example.com/capa.jpg" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining("https válido"));

    fireEvent.change(screen.getByLabelText("URL da imagem de capa"), {
      target: { value: "https://example.com/capa.jpg" },
    });
    fireEvent.change(screen.getByLabelText("Link relacionado"), {
      target: { value: "javascript:alert(1)" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining("http ou https válido"));
  });

  it("avisa quando a prévia falha sem impedir o salvamento", async () => {
    render(<EventsManager />);
    await screen.findByText("Nenhum evento encontrado.");
    fillRequiredForm();
    fireEvent.change(screen.getByLabelText("URL da imagem de capa"), {
      target: { value: createdEvent.image_url },
    });
    fireEvent.error(screen.getByRole("img", { name: "Prévia da capa do evento" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Não foi possível carregar esta imagem");
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce());
  });

  it("cria um curso inexistente, seleciona e envia no evento", async () => {
    render(<EventsManager />);
    await screen.findByText("Nenhum evento encontrado.");
    fillRequiredForm();

    fireEvent.click(screen.getByRole("button", { name: "Criar curso" }));
    fireEvent.change(screen.getByLabelText("Nome do novo curso"), {
      target: { value: "Medicina" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar" }));

    await waitFor(() => expect(mocks.createCourse).toHaveBeenCalledWith("Medicina"));
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce());
    expect(mocks.create.mock.calls[0][0]).toMatchObject({ course: "Medicina" });
  });
  it("filtra os quatro campos sem capitalização e conserva ordenação por data e título", async () => {
    mocks.list.mockResolvedValue([
      { ...createdEvent, id: "late", title: "Zeta", event_date: "2099-09-01" },
      { ...createdEvent, id: "beta", title: "Beta", event_type: "workshop", course: "Engenharia", location: "Laboratório" },
      { ...createdEvent, id: "alpha", title: "Alpha", course: "Geral" },
    ]);
    render(<EventsManager />);
    await screen.findByRole("article", { name: "Alpha" });
    const titles = () => screen.queryAllByRole("article").map(item => within(item).getByRole("heading").textContent);
    expect(titles()).toEqual(["Alpha", "Beta", "Zeta"]);
    for (const term of ["BETA", "WORKSHOP", "ENGENHARIA", "LABORATÓRIO"]) {
      fireEvent.change(screen.getByRole("textbox", { name: "Pesquisar eventos" }), { target: { value: term } });
      expect(titles()).toEqual(["Beta"]);
    }
    fireEvent.change(screen.getByRole("textbox", { name: "Pesquisar eventos" }), { target: { value: "ausente" } });
    expect(screen.getByRole("status")).toHaveTextContent("Nenhum evento encontrado.");
    expect(mocks.list).toHaveBeenCalledOnce();
  });

  it("reabre edição com datas civis e todos os campos e chama update uma vez", async () => {
    mocks.list.mockResolvedValue([createdEvent]); mocks.update.mockResolvedValue(createdEvent);
    render(<EventsManager />);
    await screen.findByRole("article", { name: createdEvent.title });
    fireEvent.click(screen.getByRole("button", { name: `Editar ${createdEvent.title}` }));
    expect(screen.getByLabelText("Título")).toHaveValue(createdEvent.title);
    expect(screen.getByRole("button", { name: /Período: 15\/08\/2099 – 17\/08\/2099/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Tipo")).toHaveTextContent("Outro");
    expect(screen.getByLabelText("Curso relacionado")).toHaveTextContent("Geral");
    expect(screen.getByLabelText("Local")).toHaveValue(createdEvent.location);
    expect(screen.getByLabelText("URL da imagem de capa")).toHaveValue(createdEvent.image_url);
    expect(screen.getByLabelText("Link relacionado")).toHaveValue(createdEvent.link_url);
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledOnce());
    expect(mocks.update).toHaveBeenCalledWith(createdEvent.id, expect.objectContaining({ event_date: "2099-08-15", event_end_date: "2099-08-17", description: null }));
    expect(mocks.create).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("valida curso curto e conserva formulário em falha de criação de curso", async () => {
    mocks.createCourse.mockRejectedValueOnce(new Error("Falha sintética do curso"));
    render(<EventsManager />); await screen.findByText("Nenhum evento encontrado."); fillRequiredForm();
    fireEvent.click(screen.getByRole("button", { name: "Criar curso" }));
    fireEvent.change(screen.getByLabelText("Nome do novo curso"), { target: { value: " X " } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar" }));
    expect(mocks.createCourse).not.toHaveBeenCalled();
    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining("2 caracteres"));
    fireEvent.change(screen.getByLabelText("Nome do novo curso"), { target: { value: "Medicina" } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar" }));
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledWith("Falha sintética do curso"));
    expect(screen.getByLabelText("Nome do novo curso")).toHaveValue("Medicina");
    expect(screen.getByLabelText("Título")).toHaveValue("Semana Acadêmica");
    expect(screen.getByLabelText("Curso relacionado")).toHaveTextContent("Geral");
  });

  it("cancelar exclusão não chama API; falha mantém item e sucesso remove após resposta", async () => {
    mocks.list.mockResolvedValue([createdEvent]); mocks.remove.mockRejectedValueOnce(new Error("Falha sintética ao excluir"));
    const user = userEvent.setup(); render(<EventsManager />);
    const trigger = await screen.findByRole("button", { name: `Excluir ${createdEvent.title}` });
    await user.click(trigger);
    expect(screen.getByRole("alertdialog")).toHaveTextContent(createdEvent.title);
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(mocks.remove).not.toHaveBeenCalled(); expect(trigger).toHaveFocus();
    await user.click(trigger); await user.click(screen.getByRole("button", { name: "Excluir" }));
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledWith("Falha sintética ao excluir"));
    expect(screen.getByRole("article", { name: createdEvent.title })).toBeInTheDocument();
    let finish!: () => void; mocks.remove.mockReturnValueOnce(new Promise<void>(resolve => { finish = resolve; }));
    await user.click(trigger); await user.click(screen.getByRole("button", { name: "Excluir" }));
    expect(screen.getByRole("article", { name: createdEvent.title })).toBeInTheDocument();
    finish(); await waitFor(() => expect(screen.queryByRole("article")).not.toBeInTheDocument());
  });

  it("salvamento pendente bloqueia envio e falha preserva campos", async () => {
    let fail!: (reason: Error) => void; mocks.create.mockReturnValueOnce(new Promise((_, reject) => { fail = reject; }));
    render(<EventsManager />); await screen.findByText("Nenhum evento encontrado."); fillRequiredForm();
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    const busy = screen.getByRole("button", { name: "Salvando..." });
    expect(busy).toBeDisabled(); expect(busy).toHaveAttribute("aria-busy", "true");
    fireEvent.click(busy); expect(mocks.create).toHaveBeenCalledOnce();
    fail(new Error("Falha sintética ao salvar"));
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledWith("Falha sintética ao salvar"));
    expect(screen.getByRole("dialog", { name: "Novo evento" })).toBeInTheDocument();
    expect(screen.getByLabelText("Título")).toHaveValue("Semana Acadêmica");
    expect(screen.getByLabelText("Local")).toHaveValue("Auditório Central");
    expect(screen.getByRole("button", { name: "Salvar" })).toBeEnabled();
  });

  it("anuncia carga e preserva toast seguido de vazio na falha", async () => {
    mocks.list.mockRejectedValueOnce(new Error("Falha sintética de carga"));
    render(<EventsManager />);
    expect(screen.getByRole("status", { name: "Carregando eventos" })).toBeInTheDocument();
    expect(await screen.findByText("Nenhum evento encontrado.")).toBeInTheDocument();
    expect(mocks.toastError).toHaveBeenCalledWith("Erro ao carregar eventos.");
  });

  it("Escape fecha formulário e retorna foco ao botão de origem sem salvar", async () => {
    const user = userEvent.setup(); render(<EventsManager />); await screen.findByText("Nenhum evento encontrado.");
    const trigger = screen.getByRole("button", { name: "Novo evento" }); await user.click(trigger);
    await user.type(screen.getByLabelText("Título"), "Rascunho sintético"); await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); expect(trigger).toHaveFocus(); expect(mocks.create).not.toHaveBeenCalled();
  });

});

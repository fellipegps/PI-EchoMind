import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
});

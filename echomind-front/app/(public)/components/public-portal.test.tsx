import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  streamPublicChat: vi.fn(),
  listFaqs: vi.fn(),
  listEvents: vi.fn(),
  listLocations: vi.fn(),
  getInstitution: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  streamPublicChat: apiMocks.streamPublicChat,
  publicPortalApi: {
    listFaqs: apiMocks.listFaqs,
    listEvents: apiMocks.listEvents,
    listLocations: apiMocks.listLocations,
    getInstitution: apiMocks.getInstitution,
  },
}));

vi.mock("./public-campus-navigator", () => ({
  PublicCampusNavigator: () => null,
}));

import { PublicPortal } from "./public-portal";

const faq = {
  id: "faq-1",
  question: "Como faço minha rematrícula?",
  answer: "Pelo portal do aluno.",
  show_in_chatbot: true,
  created_at: "2026-09-14T10:00:00Z",
};

const publicEvent = {
  id: "event-1",
  title: "Mostra de projetos reais",
  event_date: "2099-08-15",
  event_end_date: "2099-08-17",
  event_type: "evento_social",
  course: "Engenharia Civil",
  description: "Projetos desenvolvidos pelos estudantes.",
  location: "Auditório Central",
  image_url: "https://cdn.example.com/mostra.webp",
  link_url: "https://example.com/mostra",
};

const publicLocations = [
  {
    id: "portaria-principal",
    name: "Portaria Principal",
    description: "Entrada de estudantes.",
    category: "acesso",
    floor: null,
    building: "Entrada",
    x: 18,
    y: 74,
  },
  {
    id: "bloco-f",
    name: "Bloco F",
    description: "Laboratórios de tecnologia.",
    category: "laboratórios",
    floor: "1º andar",
    building: "Bloco F",
    x: 70,
    y: 30,
  },
  {
    id: "biblioteca",
    name: "Biblioteca Central",
    description: "Acervo e salas de estudo.",
    category: "estudo",
    floor: "Térreo",
    building: "Bloco B",
    x: 38,
    y: 42,
  },
  {
    id: "bloco-b",
    name: "Bloco B",
    description: "Área de saúde.",
    category: "saúde",
    floor: null,
    building: "Bloco B",
    x: 28,
    y: 18,
  },
];

describe("PublicPortal", () => {
  beforeEach(() => {
    apiMocks.streamPublicChat.mockReset();
    apiMocks.listFaqs.mockReset();
    apiMocks.listEvents.mockReset();
    apiMocks.listLocations.mockReset();
    apiMocks.getInstitution.mockReset();
    apiMocks.listFaqs.mockResolvedValue([faq]);
    apiMocks.listEvents.mockResolvedValue([publicEvent]);
    apiMocks.listLocations.mockResolvedValue(publicLocations);
    apiMocks.getInstitution.mockResolvedValue({ company_name: "UniEVANGÉLICA" });
  });

  it("carrega instituição e FAQs somente pelo slug público do link", async () => {
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    expect(await screen.findByRole("heading", { name: "UniEVANGÉLICA" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: faq.question })).toBeInTheDocument();
    expect(apiMocks.listFaqs).toHaveBeenCalledWith("unievangelica-anapolis");
    expect(apiMocks.listEvents).toHaveBeenCalledWith("unievangelica-anapolis");
    expect(apiMocks.listLocations).toHaveBeenCalledWith("unievangelica-anapolis");
    expect(apiMocks.getInstitution).toHaveBeenCalledWith("unievangelica-anapolis");
    expect(screen.getByRole("button", { name: "Chat" })).toHaveAttribute("aria-current", "page");
  });

  it("envia a pergunta ao chat real e acumula os tokens da resposta", async () => {
    const user = userEvent.setup();
    apiMocks.streamPublicChat.mockImplementation(
      async (_question, publicSlug, onToken, onDone) => {
        expect(publicSlug).toBe("unievangelica-anapolis");
        onToken("A rematrícula ");
        onToken("está disponível.");
        onDone();
      }
    );
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Qual é o prazo?");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));

    expect(screen.getByText("Qual é o prazo?")).toBeInTheDocument();
    expect(await screen.findByText("A rematrícula está disponível.")).toBeInTheDocument();
    expect(apiMocks.streamPublicChat).toHaveBeenCalledOnce();
  });

  it("formata o negrito da resposta mesmo quando os marcadores chegam em partes", async () => {
    const user = userEvent.setup();
    apiMocks.streamPublicChat.mockImplementation(async (_question, _publicSlug, onToken, onDone) => {
      onToken("Acesse o **Portal do ");
      onToken("Aluno** e consulte **Disciplinas** (Fonte: FAQ).");
      onDone();
    });
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Onde vejo minhas notas?");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));

    const portal = await screen.findByText("Portal do Aluno");
    expect(portal).toHaveProperty("tagName", "STRONG");
    expect(screen.getByText("Disciplinas")).toHaveProperty("tagName", "STRONG");
    expect(portal.closest("div")).toHaveTextContent("Acesse o Portal do Aluno e consulte Disciplinas (Fonte: FAQ).");
    expect(portal.closest("div")).not.toHaveTextContent("**");
  });

  it("bloqueia o chat e não consulta APIs quando o link não possui slug", () => {
    render(<PublicPortal />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Link inválido. Solicite à instituição o endereço correto do portal."
    );
    expect(screen.getByLabelText("Digite sua pergunta")).toBeDisabled();
    expect(apiMocks.listFaqs).not.toHaveBeenCalled();
    expect(apiMocks.listEvents).not.toHaveBeenCalled();
    expect(apiMocks.listLocations).not.toHaveBeenCalled();
    expect(apiMocks.getInstitution).not.toHaveBeenCalled();
    expect(apiMocks.streamPublicChat).not.toHaveBeenCalled();
  });

  it("mostra erro amigável quando o slug público não existe", async () => {
    apiMocks.getInstitution.mockRejectedValue(new Error("404 interno"));

    render(<PublicPortal publicSlug="instituicao-inexistente" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Instituição não encontrada. Verifique o endereço e tente novamente."
    );
    expect(screen.getByLabelText("Digite sua pergunta")).toBeDisabled();
  });

  it("mantém somente chat, eventos e locais na navegação do MVP", async () => {
    const user = userEvent.setup();
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    expect(screen.getByRole("button", { name: "Chat" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eventos" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Locais" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Avisos" })).not.toBeInTheDocument();
    expect(screen.queryByText("Avisos gerais")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Eventos" }));
    expect(screen.getByRole("heading", { name: "Próximos eventos" })).toBeInTheDocument();
    expect(screen.getByText(publicEvent.title)).toBeInTheDocument();
    expect(screen.getByText(publicEvent.location)).toBeInTheDocument();
    expect(screen.getByText(/15 a 17 de Agosto de 2099/)).toBeInTheDocument();
    expect(screen.getByText(publicEvent.course)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: publicEvent.title })).toHaveAttribute(
      "src",
      publicEvent.image_url
    );
    expect(screen.queryByText("Saiba mais")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: publicEvent.link_url })).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link", { name: publicEvent.link_url })).toHaveAttribute(
      "rel",
      "noopener noreferrer"
    );
    expect(screen.queryByText("Semana da Tecnologia")).not.toBeInTheDocument();
  });

  it("oferece uma única navegação com seleção e regiões operáveis por teclado", async () => {
    const user = userEvent.setup();
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { level: 1, name: "UniEVANGÉLICA" });
    const navigation = screen.getByRole("navigation", { name: "Navegação principal" });
    expect(within(navigation).getAllByRole("button")).toHaveLength(3);
    await user.tab();
    expect(within(navigation).getByRole("button", { name: "Chat" })).toHaveFocus();
    await user.tab();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("region", { name: "Próximos eventos" })).toBeInTheDocument();
    expect(within(navigation).getByRole("button", { name: "Eventos" })).toHaveAttribute("aria-current", "page");
    await user.tab();
    await user.keyboard(" ");
    expect(screen.getByRole("region", { name: "Locais do campus" })).toBeInTheDocument();
    expect(within(navigation).getAllByRole("button").filter((button) => button.getAttribute("aria-current") === "page")).toHaveLength(1);
  });

  it("preserva conversa pendente, tokens e rascunho ao navegar, sem repetir as consultas institucionais", async () => {
    const user = userEvent.setup();
    let onToken!: (token: string) => void;
    let onDone!: () => void;
    apiMocks.streamPublicChat.mockImplementation((_question, _slug, token, done) => {
      onToken = token;
      onDone = done;
      return Promise.resolve();
    });
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Pergunta em andamento");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    await user.click(screen.getByRole("button", { name: "Eventos" }));
    await act(async () => onToken("Resposta parcial "));
    await user.click(screen.getByRole("button", { name: "Locais" }));
    await user.click(screen.getByRole("button", { name: "Chat" }));
    expect(screen.getByText("Pergunta em andamento")).toBeInTheDocument();
    expect(screen.getByText("Resposta parcial")).toBeInTheDocument();
    expect(screen.getByLabelText("Digite sua pergunta")).toBeDisabled();
    await act(async () => { onToken("preservada."); onDone(); });
    expect(screen.getByText("Resposta parcial preservada.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Rascunho preservado");
    const input = screen.getByLabelText("Digite sua pergunta");
    fireEvent.resize(window);
    expect(screen.getByLabelText("Digite sua pergunta")).toBe(input);
    await user.click(screen.getByRole("button", { name: "Eventos" }));
    await user.click(screen.getByRole("button", { name: "Chat" }));
    expect(screen.getByLabelText("Digite sua pergunta")).toHaveValue("Rascunho preservado");
    expect(screen.getByText("Resposta parcial preservada.")).toBeInTheDocument();
    for (const query of [apiMocks.getInstitution, apiMocks.listFaqs, apiMocks.listEvents, apiMocks.listLocations]) {
      expect(query).toHaveBeenCalledOnce();
      expect(query).toHaveBeenCalledWith("unievangelica-anapolis");
    }
    expect(apiMocks.streamPublicChat).toHaveBeenCalledOnce();
  });

  it("remove a capa quebrada e mantém o card do evento", async () => {
    const user = userEvent.setup();
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    await user.click(screen.getByRole("button", { name: "Eventos" }));
    const cover = await screen.findByRole("img", { name: publicEvent.title });
    fireEvent.error(cover);

    expect(screen.queryByRole("img", { name: publicEvent.title })).not.toBeInTheDocument();
    expect(screen.getByText(publicEvent.title)).toBeInTheDocument();
  });

  it("trata lista vazia e falha de eventos sem expor detalhes internos", async () => {
    const user = userEvent.setup();
    apiMocks.listEvents.mockResolvedValueOnce([]);
    const { unmount } = render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    await user.click(screen.getByRole("button", { name: "Eventos" }));
    expect(await screen.findByText("Nenhum evento programado no momento.")).toBeInTheDocument();
    unmount();

    apiMocks.listEvents.mockRejectedValueOnce(new Error("segredo interno"));
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await user.click(screen.getByRole("button", { name: "Eventos" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar os eventos agora."
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("segredo interno");
  });

  it("pesquisa locais, seleciona origem e calcula rota aproximada", async () => {
    const user = userEvent.setup();
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    await user.click(screen.getByRole("button", { name: "Locais" }));
    await user.selectOptions(screen.getByLabelText("Ponto de origem"), "portaria-principal");
    await user.click(
      screen.getByRole("button", { name: "Selecionar Bloco F como destino" })
    );
    await user.click(screen.getByRole("button", { name: "Traçar rota" }));

    expect(screen.getByText("Portaria Principal → Bloco F")).toBeInTheDocument();
    expect(screen.getByText(/Aproximadamente \d+ m · \d+ min a pé/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Buscar local"), "biblioteca");
    expect(
      screen.getByRole("button", { name: "Selecionar Biblioteca Central como destino" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Selecionar Bloco B como destino" })
    ).not.toBeInTheDocument();
  });

  it("trata lista vazia e erro seguro ao carregar locais reais", async () => {
    const user = userEvent.setup();
    apiMocks.listLocations.mockResolvedValueOnce([]);
    const { unmount } = render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    await user.click(screen.getByRole("button", { name: "Locais" }));
    expect(await screen.findByText("Nenhum local disponível no momento.")).toBeInTheDocument();
    unmount();

    apiMocks.listLocations.mockRejectedValueOnce(new Error("segredo interno"));
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await user.click(screen.getByRole("button", { name: "Locais" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar os locais agora."
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("segredo interno");
  });

  it("mostra erro seguro quando o streaming falha", async () => {
    const user = userEvent.setup();
    apiMocks.streamPublicChat.mockImplementation(
      async (_question, _publicSlug, _onToken, _onDone, onError) => {
        onError(new Error("segredo interno"));
      }
    );
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Teste");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Não foi possível obter uma resposta agora. Tente novamente em instantes."
      );
    });
    expect(screen.getByRole("alert")).not.toHaveTextContent("segredo interno");
  });
});

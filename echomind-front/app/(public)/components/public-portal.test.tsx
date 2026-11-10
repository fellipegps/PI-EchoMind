import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  streamPublicChat: vi.fn(),
  submitPublicUnanswered: vi.fn(),
  listFaqs: vi.fn(),
  listEvents: vi.fn(),
  getInstitution: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  streamPublicChat: apiMocks.streamPublicChat,
  submitPublicUnanswered: apiMocks.submitPublicUnanswered,
  publicPortalApi: {
    listFaqs: apiMocks.listFaqs,
    listEvents: apiMocks.listEvents,
    getInstitution: apiMocks.getInstitution,
  },
}));

vi.mock("./public-campus-navigator", () => ({
  PublicCampusNavigator: ({ publicSlug }: { publicSlug: string }) => <div role="region" aria-label="Navegação geográfica do campus">{publicSlug}</div>,
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

describe("PublicPortal", () => {
  it("retorna diretamente à lista de locais depois de consultar uma ficha", async () => {
    render(<PublicPortal publicSlug="universidade" initialTab="locais" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    expect(screen.getByRole("button", { name: "Locais" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("region", { name: "Navegação geográfica do campus" })).toHaveTextContent("universidade");
    expect(screen.queryByRole("textbox", { name: "Digite sua pergunta" })).not.toBeInTheDocument();
  });
  it("permite conversar sem aviso completo, mantendo as abas de eventos e locais", async () => {
    apiMocks.getInstitution.mockResolvedValue({ company_name: "Instituição", privacy_ready: false });
    render(<PublicPortal publicSlug="instituicao" />);
    await screen.findByRole("heading", { name: "Instituição" });
    const input = screen.getByRole("textbox", { name: "Digite sua pergunta" });
    expect(input).toBeEnabled();
    await userEvent.type(input, "Onde fica a secretaria?");
    expect(screen.getByRole("button", { name: "Enviar pergunta" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    expect(apiMocks.streamPublicChat).toHaveBeenCalledWith("Onde fica a secretaria?", "instituicao", expect.any(Function), expect.any(Function), expect.any(Function));
    expect(screen.getByRole("button", { name: "Eventos" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Locais" })).toBeEnabled();
  });
  it("informa o uso dos dados antes do envio e oferece o aviso de privacidade", async () => {
    render(<PublicPortal publicSlug="universidade" />);
    const input = await screen.findByRole("textbox", { name: "Digite sua pergunta" });
    expect(input).toHaveAccessibleDescription(/armazenadas.*Groq/);
    expect(input).toHaveAttribute("maxLength", "2000");
    expect(screen.getByRole("link", { name: "Saiba como seus dados são usados" })).toHaveAttribute("href", "/p/universidade/privacidade");
  });
  it("oferece somente o navegador geográfico na aba Locais", async () => {
    render(<PublicPortal publicSlug="universidade" />);
    await userEvent.click(screen.getByRole("button", { name: "Locais" }));
    expect(screen.getByRole("region", { name: "Navegação geográfica do campus" })).toHaveTextContent("universidade");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button").map(button => button.textContent?.trim())).toEqual(["Chat", "Eventos", "Locais"]);
  });
  beforeEach(() => {
    apiMocks.streamPublicChat.mockReset();
    apiMocks.submitPublicUnanswered.mockReset();
    apiMocks.submitPublicUnanswered.mockResolvedValue(undefined);
    apiMocks.listFaqs.mockReset();
    apiMocks.listEvents.mockReset();
    apiMocks.getInstitution.mockReset();
    apiMocks.listFaqs.mockResolvedValue([faq]);
    apiMocks.listEvents.mockResolvedValue([publicEvent]);
    apiMocks.getInstitution.mockResolvedValue({ company_name: "UniEVANGÉLICA", privacy_ready: true });
  });

  it("carrega instituição e FAQs somente pelo slug público do link", async () => {
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);

    expect(await screen.findByRole("heading", { name: "UniEVANGÉLICA" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: faq.question })).toBeInTheDocument();
    expect(apiMocks.listFaqs).toHaveBeenCalledWith("unievangelica-anapolis");
    expect(apiMocks.listEvents).toHaveBeenCalledWith("unievangelica-anapolis");
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

  it("somente encaminha após confirmar, desabilita duplo clique e mostra sucesso", async () => {
    let finish!: () => void;
    apiMocks.submitPublicUnanswered.mockReturnValue(new Promise<void>(resolve => { finish = resolve; }));
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, done) => {
      token("Não tenho essa informação."); done({ unanswered_token: "a".repeat(43) });
    });
    const user = userEvent.setup();
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Qual é o prazo?");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    const group = await screen.findByRole("group", { name: "Encaminhamento da pergunta" });
    expect(apiMocks.submitPublicUnanswered).not.toHaveBeenCalled();
    expect(screen.getByText(/A conversa continua no histórico/)).toBeInTheDocument();
    const send = within(group).getByRole("button", { name: "Enviar pergunta" });
    fireEvent.click(send); fireEvent.click(send);
    expect(send).toBeDisabled();
    expect(within(group).getByRole("button", { name: "Agora não" })).toBeDisabled();
    expect(apiMocks.submitPublicUnanswered).toHaveBeenCalledExactlyOnceWith("unievangelica-anapolis", "a".repeat(43));
    await act(async () => finish());
    expect(await screen.findByText("Pergunta encaminhada para análise da equipe.")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Encaminhamento da pergunta" })).not.toBeInTheDocument();
  });

  it("Agora não fecha a opção sem encaminhar a pergunta", async () => {
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, done) => {
      token("Não tenho essa informação."); done({ unanswered_token: "a".repeat(43) });
    });
    const user = userEvent.setup();
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Qual o prazo?");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    await user.click(await screen.findByRole("button", { name: "Agora não" }));
    expect(screen.queryByRole("group", { name: "Encaminhamento da pergunta" })).not.toBeInTheDocument();
    expect(apiMocks.submitPublicUnanswered).not.toHaveBeenCalled();
    expect(screen.getByText("Não tenho essa informação.")).toBeInTheDocument();
  });

  it("mantém a confirmação na resposta correta e permite tentar novamente após falha", async () => {
    apiMocks.submitPublicUnanswered.mockRejectedValueOnce(new Error("Falha sintética"));
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, done) => {
      token("Resposta sem informação."); done({ unanswered_token: "a".repeat(43) });
    });
    const user = userEvent.setup();
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Qual o prazo?");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, done) => { token("Resposta conhecida."); done(); });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Onde fica o campus?");
    await user.click(screen.getByLabelText("Digite sua pergunta").closest("form")!.querySelector("button")!);
    const original = screen.getByText("Resposta sem informação.").closest("article")!;
    const latest = screen.getByText("Resposta conhecida.").closest("article")!;
    expect(within(latest).queryByRole("group")).not.toBeInTheDocument();
    await user.click(within(original).getByRole("button", { name: "Enviar pergunta" }));
    expect(await within(original).findByRole("alert")).toHaveTextContent("Não foi possível encaminhar");
    await user.click(within(original).getByRole("button", { name: "Enviar pergunta" }));
    expect(await within(original).findByText("Pergunta encaminhada para análise da equipe.")).toBeInTheDocument();
    expect(apiMocks.submitPublicUnanswered).toHaveBeenCalledTimes(2);
  });

  it("não oferece encaminhamento em resposta conhecida ou falha técnica", async () => {
    const user = userEvent.setup();
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, done) => { token("Resposta conhecida."); done({ unanswered_token: null }); });
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Qual o prazo?");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    expect(screen.queryByRole("button", { name: "Agora não" })).not.toBeInTheDocument();
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, _done, error) => { token("Resposta parcial."); error(new Error("Interrupção")); });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Outra dúvida");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível obter uma resposta");
    expect(screen.queryByRole("button", { name: "Agora não" })).not.toBeInTheDocument();
    expect(apiMocks.submitPublicUnanswered).not.toHaveBeenCalled();
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
    for (const query of [apiMocks.getInstitution, apiMocks.listFaqs, apiMocks.listEvents]) {
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
    expect(screen.queryByText("Buscando a melhor resposta...")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Digite sua pergunta")).toBeEnabled();
  });

  it("bloqueia sugestões durante carga institucional e não envia campo vazio", async () => {
    const user = userEvent.setup();
    let resolveInstitution!: (value: { company_name: string }) => void;
    apiMocks.getInstitution.mockReturnValue(new Promise((resolve) => { resolveInstitution = resolve; }));
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    const suggestion = await screen.findByRole("button", { name: faq.question });
    expect(suggestion).toBeDisabled();
    expect(screen.getByRole("button", { name: `Perguntar: ${faq.question}` })).toBeDisabled();
    expect(screen.getByLabelText("Digite sua pergunta")).toBeDisabled();
    await user.click(suggestion);
    fireEvent.submit(screen.getByRole("button", { name: "Enviar pergunta" }).closest("form")!);
    expect(apiMocks.streamPublicChat).not.toHaveBeenCalled();
    await act(async () => resolveInstitution({ company_name: "UniEVANGÉLICA" }));
    await user.type(screen.getByLabelText("Digite sua pergunta"), "   ");
    fireEvent.submit(screen.getByRole("button", { name: "Enviar pergunta" }).closest("form")!);
    expect(apiMocks.streamPublicChat).not.toHaveBeenCalled();
  });

  it("anuncia espera, bloqueia envio simultâneo e termina uma única resposta incremental", async () => {
    const user = userEvent.setup();
    let token!: (value: string) => void;
    let done!: () => void;
    apiMocks.streamPublicChat.mockImplementation((_question, _slug, onToken, onDone) => {
      token = onToken; done = onDone; return Promise.resolve();
    });
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "  Pergunta de teste  ");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    expect(screen.getByRole("status")).toHaveTextContent("Buscando a melhor resposta...");
    expect(screen.getByRole("button", { name: faq.question })).toBeDisabled();
    expect(screen.getByLabelText("Digite sua pergunta")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Enviar pergunta" }).closest("form")).toHaveAttribute("aria-busy", "true");
    await user.click(screen.getByRole("button", { name: `Perguntar: ${faq.question}` }));
    await act(async () => token(""));
    expect(screen.getByRole("status")).toBeInTheDocument();
    await act(async () => token("Primeiro "));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    const response = screen.getAllByRole("article", { name: "Resposta do assistente" }).at(-1);
    await act(async () => { token("segundo."); done(); });
    expect(screen.getAllByRole("article", { name: "Resposta do assistente" })).toHaveLength(2);
    expect(response).toHaveTextContent("Primeiro segundo.");
    expect(screen.getByLabelText("Digite sua pergunta")).toBeEnabled();
    expect(apiMocks.streamPublicChat).toHaveBeenCalledOnce();
    expect(apiMocks.streamPublicChat.mock.calls[0].slice(0, 2)).toEqual(["Pergunta de teste", "unievangelica-anapolis"]);
  });

  it("mantém listas e código em Markdown e descarta HTML e destinos executáveis", async () => {
    const user = userEvent.setup();
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, done) => {
      token("**Ne");
      token("grito**\n\n- Item seguro\n\n```js\nconst texto = '");
      token("teste';\n```\n\n[Seguro](https://example.com) [Inseguro](javascript:alert%281%29)\n\n<script>alert('interno')</script><img src=x onerror=alert(1)>");
      done();
    });
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    await user.type(screen.getByLabelText("Digite sua pergunta"), "Markdown");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    const log = screen.getByRole("log", { name: "Conversa com o assistente" });
    expect(within(log).getByText("Negrito").tagName).toBe("STRONG");
    expect(within(log).getByRole("listitem")).toHaveTextContent("Item seguro");
    expect(log.querySelector("pre code")).toHaveTextContent("const texto = 'teste';");
    expect(within(log).getByRole("region", { name: "Código da resposta" })).toHaveAttribute("tabindex", "0");
    expect(within(log).getByRole("link", { name: "Seguro" })).toHaveAttribute("href", "https://example.com");
    expect(within(log).getByText("Inseguro")).not.toHaveAttribute("href", expect.stringMatching(/javascript:/i));
    expect(log.querySelector("script, img, iframe")).toBeNull();
  });

  it("usa os dados já consultados no auxiliar e a FAQ envia pelo contrato comum", async () => {
    const user = userEvent.setup();
    apiMocks.streamPublicChat.mockImplementation(async (_question, _slug, token, done) => { token("Resposta da instituição."); done(); });
    apiMocks.listFaqs.mockResolvedValue(Array.from({ length: 6 }, (_, index) => ({ ...faq, id: `faq-${index}`, question: `Pergunta institucional ${index}` })));
    render(<PublicPortal publicSlug="unievangelica-anapolis" />);
    await screen.findByRole("heading", { name: "UniEVANGÉLICA" });
    const auxiliary = screen.getByRole("complementary", { name: "Informações da instituição" });
    expect(within(auxiliary).getAllByRole("button", { name: /^Perguntar:/ })).toHaveLength(4);
    expect(within(auxiliary).getByText(publicEvent.title)).toBeInTheDocument();
    await user.click(within(auxiliary).getByRole("button", { name: "Perguntar: Pergunta institucional 0" }));
    expect(apiMocks.streamPublicChat.mock.calls[0].slice(0, 2)).toEqual(["Pergunta institucional 0", "unievangelica-anapolis"]);
    await user.click(within(auxiliary).getByRole("button", { name: "Ver eventos" }));
    expect(screen.getByRole("region", { name: "Próximos eventos" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chat" }));
    for (const query of [apiMocks.getInstitution, apiMocks.listFaqs, apiMocks.listEvents]) expect(query).toHaveBeenCalledOnce();
    expect(screen.queryByText("Pergunta institucional 4")).not.toBeInTheDocument();
  });
});

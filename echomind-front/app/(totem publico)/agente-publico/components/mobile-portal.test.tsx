import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  streamChat: vi.fn(),
  listTotem: vi.fn(),
  getPublic: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  streamChat: apiMocks.streamChat,
  faqApi: { listTotem: apiMocks.listTotem },
  configApi: { getPublic: apiMocks.getPublic },
}));

import { MobilePortal } from "./mobile-portal";

const faq = {
  id: "faq-1",
  question: "Como faço minha rematrícula?",
  answer: "Pelo portal do aluno.",
  show_on_totem: true,
  created_at: "2026-09-14T10:00:00Z",
};

describe("MobilePortal", () => {
  beforeEach(() => {
    apiMocks.streamChat.mockReset();
    apiMocks.listTotem.mockReset();
    apiMocks.getPublic.mockReset();
    apiMocks.listTotem.mockResolvedValue([faq]);
    apiMocks.getPublic.mockResolvedValue({ company_name: "UniEVANGÉLICA" });
    window.history.replaceState({}, "", "/agente-publico?tenant=tenant-a");
  });

  it("carrega configuração e FAQs somente para o tenant presente no link", async () => {
    render(<MobilePortal />);

    expect(await screen.findByRole("heading", { name: "UniEVANGÉLICA" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: faq.question })).toBeInTheDocument();
    expect(apiMocks.listTotem).toHaveBeenCalledWith("tenant-a");
    expect(apiMocks.getPublic).toHaveBeenCalledWith("tenant-a");
    expect(screen.getByRole("button", { name: "Chat" })).toHaveAttribute("aria-current", "page");
  });

  it("envia a pergunta ao chat real e acumula os tokens da resposta", async () => {
    const user = userEvent.setup();
    apiMocks.streamChat.mockImplementation(
      async (_question, tenantId, onToken, onDone) => {
        expect(tenantId).toBe("tenant-a");
        onToken("A rematrícula ");
        onToken("está disponível.");
        onDone();
      }
    );
    render(<MobilePortal />);

    await user.type(screen.getByLabelText("Digite sua pergunta"), "Qual é o prazo?");
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));

    expect(screen.getByText("Qual é o prazo?")).toBeInTheDocument();
    expect(await screen.findByText("A rematrícula está disponível.")).toBeInTheDocument();
    expect(apiMocks.streamChat).toHaveBeenCalledOnce();
  });

  it("bloqueia o chat e não consulta APIs quando o link não possui tenant", () => {
    window.history.replaceState({}, "", "/agente-publico");

    render(<MobilePortal />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Link inválido. Solicite à instituição o endereço correto do portal."
    );
    expect(screen.getByLabelText("Digite sua pergunta")).toBeDisabled();
    expect(apiMocks.listTotem).not.toHaveBeenCalled();
    expect(apiMocks.getPublic).not.toHaveBeenCalled();
    expect(apiMocks.streamChat).not.toHaveBeenCalled();
  });

  it("troca entre avisos e eventos pela navegação responsiva", async () => {
    const user = userEvent.setup();
    render(<MobilePortal />);

    await user.click(screen.getByRole("button", { name: "Avisos" }));
    expect(screen.getByRole("heading", { name: "Avisos gerais" })).toBeInTheDocument();
    expect(screen.getByText("Prazo para rematrícula")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Eventos" }));
    expect(screen.getByRole("heading", { name: "Próximos eventos" })).toBeInTheDocument();
    expect(screen.getByText("Semana da Tecnologia")).toBeInTheDocument();
  });

  it("pesquisa locais, seleciona origem e calcula rota aproximada", async () => {
    const user = userEvent.setup();
    render(<MobilePortal />);

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

  it("mostra erro seguro quando o streaming falha", async () => {
    const user = userEvent.setup();
    apiMocks.streamChat.mockImplementation(
      async (_question, _tenantId, _onToken, _onDone, onError) => {
        onError(new Error("segredo interno"));
      }
    );
    render(<MobilePortal />);

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

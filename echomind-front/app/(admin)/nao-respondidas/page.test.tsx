import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  approve: vi.fn(),
  ignore: vi.fn(),
  restore: vi.fn(),
  convert: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  unansweredApi: {
    list: mocks.list,
    approve: mocks.approve,
    ignore: mocks.ignore,
    restore: mocks.restore,
    convert: mocks.convert,
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import UnansweredQuestions from "./page";
import { toast } from "sonner";

const pending = {
  id: "pending-1",
  canonical_question: "Onde vejo minhas notas?",
  count: 2,
  first_asked: "2026-10-01T10:00:00Z",
  last_asked: "2026-10-02T10:00:00Z",
  similar_questions: [],
  triage_status: "pending",
  triage_reason: null,
};
const review = {
  ...pending,
  id: "review-1",
  canonical_question: "Que porra é o prazo de matrícula?",
  count: 1,
  triage_status: "review",
  triage_reason: "abusive_language",
};

describe("Perguntas Não Respondidas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.convert.mockReset().mockResolvedValue(undefined);
    mocks.list.mockImplementation(async (status) =>
      status === "pending" ? [pending] : status === "review" ? [review] : []
    );
    mocks.approve.mockResolvedValue(undefined);
    mocks.ignore.mockResolvedValue(undefined);
    mocks.restore.mockResolvedValue(undefined);
  });

  it("separa revisão das pendentes e permite aprovação humana", async () => {
    const user = userEvent.setup();
    render(<UnansweredQuestions />);

    expect(await screen.findByText(pending.canonical_question)).toBeInTheDocument();
    expect(screen.queryByText(review.canonical_question)).not.toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledWith("pending");
    expect(mocks.list).toHaveBeenCalledWith("review");
    expect(mocks.list).toHaveBeenCalledWith("ignored");

    await user.click(screen.getByRole("button", { name: "Revisar (1)" }));
    expect(screen.getByText(review.canonical_question)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Responder" })).not.toBeInTheDocument();
    expect(screen.getByText("Revisão necessária: linguagem inadequada.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Enviar para pendentes" }));
    await waitFor(() => expect(mocks.approve).toHaveBeenCalledWith("review-1"));
    expect(screen.getByRole("button", { name: "Revisar (0)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pendentes (2)" }));
    expect(screen.getByText(review.canonical_question)).toBeInTheDocument();
  });

  it("ignora uma pergunta e permite restaurá-la", async () => {
    const user = userEvent.setup();
    render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);

    await user.click(screen.getByRole("button", { name: "Ignorar pergunta" }));
    await user.click(screen.getByRole("button", { name: /^Ignorar$/ }));

    await waitFor(() => expect(mocks.ignore).toHaveBeenCalledWith("pending-1"));
    expect(screen.queryByText(pending.canonical_question)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ignoradas (1)" }));
    expect(screen.getByText(pending.canonical_question)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restaurar" }));
    await waitFor(() => expect(mocks.restore).toHaveBeenCalledWith("pending-1"));
    await user.click(screen.getByRole("button", { name: "Pendentes (1)" }));
    expect(screen.getByText(pending.canonical_question)).toBeInTheDocument();
  });
  it("nomeia carga e conserva toast seguido de vazio em falha de carga", async () => {
    mocks.list.mockRejectedValue(new Error("falha sintética"));
    render(<UnansweredQuestions />);
    expect(screen.getByRole("status", { name: "Carregando perguntas" })).toBeInTheDocument();
    expect(await screen.findByText("Nenhuma pergunta pendente.")).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith("Erro ao carregar perguntas.");
    expect(mocks.list).toHaveBeenCalledTimes(3);
  });

  it("busca canônica e variações sem capitalização dentro do status e expande detalhes por teclado", async () => {
    const item = { ...pending, similar_questions: ["CONSULTAR HISTÓRICO ACADÊMICO", "Outra formulação extensa"] };
    const ignored = { ...pending, id: "ignored-1", canonical_question: "Mensagem ignorada", triage_status: "ignored", triage_reason: "ignored_by_admin" };
    mocks.list.mockImplementation(async (status) => status === "pending" ? [item] : status === "review" ? [review] : [ignored]);
    const user = userEvent.setup();
    render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);
    const expand = screen.getByRole("button", { name: "Ver 2 variações detectadas" });
    expand.focus(); await user.keyboard("{Enter}");
    expect(expand).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("list", { name: "Variações detectadas" })).toHaveTextContent(item.similar_questions[0]);
    expect(screen.getByText("Primeira vez: 01/10/2026")).toBeInTheDocument();
    expect(screen.getByText("Última vez: 02/10/2026")).toBeInTheDocument();
    const search = screen.getByRole("textbox", { name: "Buscar por pergunta ou variação" });
    await user.type(search, "histórico acadêmico");
    expect(screen.getByRole("article", { name: pending.canonical_question })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Revisar (1)" }));
    expect(screen.getByText("Nenhum resultado para esta busca.")).toBeInTheDocument();
    await user.clear(search);
    expect(screen.getByRole("article", { name: review.canonical_question })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Responder" })).not.toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(3);
  });

  it("aprovação com falha mantém revisão e contagens até sucesso", async () => {
    mocks.approve.mockRejectedValueOnce(new Error("Falha ao aprovar."));
    const user = userEvent.setup(); render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);
    await user.click(screen.getByRole("button", { name: "Revisar (1)" }));
    await user.click(screen.getByRole("button", { name: "Enviar para pendentes" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha ao aprovar."));
    expect(screen.getByRole("article", { name: review.canonical_question })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pendentes (1)" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Responder" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Enviar para pendentes" }));
    expect(screen.getByRole("button", { name: "Pendentes (2)" })).toBeInTheDocument();
  });

  it("cancelar ignorar não altera dados e falha preserva pergunta e status", async () => {
    mocks.ignore.mockRejectedValueOnce(new Error("Falha ao ignorar."));
    const user = userEvent.setup(); render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);
    const trigger = screen.getByRole("button", { name: "Ignorar pergunta" });
    await user.click(trigger);
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Repetições iguais e as variações já identificadas também serão ignoradas.");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(mocks.ignore).not.toHaveBeenCalled(); expect(trigger).toHaveFocus();
    await user.click(trigger); await user.click(screen.getByRole("button", { name: /^Ignorar$/ }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha ao ignorar."));
    expect(screen.getByRole("article", { name: pending.canonical_question })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ignoradas (0)" })).toBeInTheDocument();
  });

  it("restaurar com falha mantém ignorada e sucesso muda para pendentes", async () => {
    const ignored = { ...pending, id: "ignored-1", triage_status: "ignored", triage_reason: "ignored_by_admin" };
    mocks.list.mockImplementation(async (status) => status === "ignored" ? [ignored] : []);
    mocks.restore.mockRejectedValueOnce(new Error("Falha ao restaurar."));
    const user = userEvent.setup(); render(<UnansweredQuestions />);
    await screen.findByText("Nenhuma pergunta pendente.");
    await user.click(screen.getByRole("button", { name: "Ignoradas (1)" }));
    expect(screen.getByText("Ignorada pelo administrador.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restaurar" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha ao restaurar."));
    expect(screen.getByRole("article", { name: pending.canonical_question })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pendentes (0)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restaurar" }));
    expect(mocks.restore).toHaveBeenLastCalledWith("ignored-1");
    expect(screen.getByRole("button", { name: "Pendentes (1)" })).toBeInTheDocument();
  });

  it("valida campos não vazios antes da conversão", async () => {
    const user = userEvent.setup(); render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);
    await user.click(screen.getByRole("button", { name: "Responder" }));
    await user.click(screen.getByRole("button", { name: "Salvar no FAQ" }));
    expect(toast.error).toHaveBeenCalledWith("Por favor, escreva uma resposta.");
    await user.type(screen.getByRole("textbox", { name: "Resposta" }), "Resposta sintética");
    await user.clear(screen.getByRole("textbox", { name: "Pergunta (editável)" }));
    await user.click(screen.getByRole("button", { name: "Salvar no FAQ" }));
    expect(toast.error).toHaveBeenCalledWith("Por favor, verifique a pergunta.");
    expect(mocks.convert).not.toHaveBeenCalled(); expect(mocks.push).not.toHaveBeenCalled();
  });

  it("conversão com falha mantém contexto e sucesso usa contrato e destino existentes", async () => {
    mocks.convert.mockRejectedValueOnce(new Error("Falha ao converter."));
    const user = userEvent.setup(); render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);
    await user.click(screen.getByRole("button", { name: "Responder" }));
    const question = screen.getByRole("textbox", { name: "Pergunta (editável)" });
    const answer = screen.getByRole("textbox", { name: "Resposta" });
    await user.clear(question); await user.type(question, "  Pergunta editada?  "); await user.type(answer, "  Resposta com espaços preservados.  ");
    await user.click(screen.getByRole("button", { name: "Salvar no FAQ" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha ao converter."));
    expect(question).toHaveValue("  Pergunta editada?  "); expect(answer).toHaveValue("  Resposta com espaços preservados.  ");
    expect(screen.getByRole("article", { name: pending.canonical_question, hidden: true })).toBeInTheDocument();
    expect(mocks.push).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Salvar no FAQ" }));
    expect(mocks.convert).toHaveBeenLastCalledWith("pending-1", "  Resposta com espaços preservados.  ", "Pergunta editada?");
    expect(mocks.push).toHaveBeenCalledWith("/base-de-conhecimento");
    expect(screen.getByRole("button", { name: "Pendentes (0)" })).toBeInTheDocument();
  });

  it("bloqueia botão de salvamento enquanto a conversão aguarda resposta", async () => {
    let finish!: () => void;
    mocks.convert.mockReturnValueOnce(new Promise<void>(resolve => { finish = resolve; }));
    const user = userEvent.setup(); render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);
    await user.click(screen.getByRole("button", { name: "Responder" }));
    await user.type(screen.getByRole("textbox", { name: "Resposta" }), "Resposta sintética");
    await user.click(screen.getByRole("button", { name: "Salvar no FAQ" }));
    const saving = screen.getByRole("button", { name: "Salvando…" });
    expect(saving).toBeDisabled(); expect(saving).toHaveAttribute("aria-busy", "true");
    await user.click(saving); expect(mocks.convert).toHaveBeenCalledTimes(1); expect(mocks.push).not.toHaveBeenCalled();
    finish(); await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/base-de-conhecimento"));
  });

  it("limpar repõe pergunta canônica e fechar limpa campos sem converter", async () => {
    const user = userEvent.setup(); render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);
    const trigger = screen.getByRole("button", { name: "Responder" }); await user.click(trigger);
    const dialog = screen.getByRole("dialog");
    await user.clear(within(dialog).getByRole("textbox", { name: "Pergunta (editável)" }));
    await user.type(within(dialog).getByRole("textbox", { name: "Resposta" }), "Rascunho");
    await user.click(screen.getByRole("button", { name: "Limpar" }));
    expect(screen.getByRole("textbox", { name: "Pergunta (editável)" })).toHaveValue(pending.canonical_question);
    expect(screen.getByRole("textbox", { name: "Resposta" })).toHaveValue("");
    await user.keyboard("{Escape}"); expect(trigger).toHaveFocus(); await user.click(trigger);
    expect(screen.getByRole("textbox", { name: "Resposta" })).toHaveValue("");
    expect(mocks.convert).not.toHaveBeenCalled();
  });

});

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Faq } from "@/lib/api";

const api = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), toggleChatbot: vi.fn() }));
const feedback = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }));
vi.mock("@/lib/api", () => ({ faqApi: api }));
vi.mock("sonner", () => ({ toast: feedback }));
import { FaqTab } from "./faq-tab";

const first: Faq = { id: "faq-1", question: "Como fazer a MATRÍCULA?", answer: "Compareça à secretaria com o comprovante.", show_in_chatbot: false, created_at: "2026-10-12T12:00:00Z" };
const second: Faq = { ...first, id: "faq-2", question: "Qual o horário da biblioteca?", answer: "A biblioteca atende até 22h; matrícula disponível na secretaria.", show_in_chatbot: true };
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
async function loaded() {
  render(<FaqTab />);
  await screen.findByRole("heading", { name: first.question });
  return userEvent.setup();
}
async function newForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Nova FAQ" }));
  await user.type(screen.getByRole("textbox", { name: "Pergunta" }), "Nova pergunta");
  await user.type(screen.getByRole("textbox", { name: "Resposta" }), "Nova resposta");
}

beforeEach(() => {
  vi.resetAllMocks();
  api.list.mockResolvedValue([first, second]);
});

describe("FaqTab com useFaqs e API simulada", () => {
  it("expõe carregamento pendente e depois conserva perguntas/respostas completas", async () => {
    const request = deferred<Faq[]>();
    api.list.mockReturnValue(request.promise);
    render(<FaqTab />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando FAQs...");
    expect(screen.queryByRole("list", { name: "Perguntas frequentes" })).not.toBeInTheDocument();
    await act(async () => request.resolve([first]));
    expect(screen.getByRole("heading", { name: first.question })).toBeInTheDocument();
    expect(screen.getByText(first.answer)).toBeInTheDocument();
  });

  it("busca só a pergunta, sem distinguir capitalização, e diferencia busca sem resultado", async () => {
    const user = await loaded();
    await user.type(screen.getByRole("textbox", { name: "Buscar por pergunta" }), "matrícula");
    expect(screen.getByRole("heading", { name: first.question })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: second.question })).not.toBeInTheDocument();
    await user.clear(screen.getByRole("textbox", { name: "Buscar por pergunta" }));
    await user.type(screen.getByRole("textbox", { name: "Buscar por pergunta" }), "COMPROVANTE");
    expect(screen.getByRole("status")).toHaveTextContent("Nenhuma pergunta encontrada");
    expect(api.list).toHaveBeenCalledTimes(1);
  });

  it("apresenta vazio neutro e preserva o toast de falha de listagem", async () => {
    api.list.mockRejectedValue(new Error("Falha sintética"));
    render(<FaqTab />);
    expect(await screen.findByText("Nenhuma FAQ disponível nesta lista")).toBeInTheDocument();
    expect(feedback.error).toHaveBeenCalledWith("Erro ao carregar FAQs.");
    expect(screen.queryByText("Nenhuma FAQ cadastrada")).not.toBeInTheDocument();
  });

  it("apresenta o mesmo vazio neutro quando a API retorna lista vazia", async () => {
    api.list.mockResolvedValue([]);
    render(<FaqTab />);
    expect(await screen.findByText("Nenhuma FAQ disponível nesta lista")).toBeInTheDocument();
    expect(feedback.error).not.toHaveBeenCalled();
  });

  it("valida ambos os campos não vazios sem enviar à API", async () => {
    const user = await loaded();
    await user.click(screen.getByRole("button", { name: "Nova FAQ" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await user.type(screen.getByRole("textbox", { name: "Pergunta" }), "Pergunta");
    await user.type(screen.getByRole("textbox", { name: "Resposta" }), "   ");
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(api.create).not.toHaveBeenCalled();
    expect(feedback.error).toHaveBeenCalledWith("Preencha todos os campos");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("bloqueia envios, campos e saídas enquanto salva; cria oculta e fecha após sucesso", async () => {
    const request = deferred<Faq>();
    api.create.mockReturnValue(request.promise);
    const user = await loaded();
    await newForm(user);
    const form = screen.getByRole("form", { name: "Formulário de FAQ" });
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(api.create).toHaveBeenCalledTimes(1);
    expect(api.create).toHaveBeenCalledWith({ question: "Nova pergunta", answer: "Nova resposta", show_in_chatbot: false });
    expect(screen.getByRole("textbox", { name: "Pergunta" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Resposta" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Fechar formulário de FAQ" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Salvando..." })).toBeDisabled();
    expect(form).toHaveAttribute("aria-busy", "true");
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await act(async () => request.resolve({ ...first, id: "created", question: "Nova pergunta", answer: "Nova resposta" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Nova pergunta" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nova FAQ" })).toHaveFocus();
  });

  it("mantém edição e conteúdo em falha; atualiza somente o ID correto no sucesso", async () => {
    api.update.mockRejectedValueOnce(new Error("Erro de edição simulado"));
    const user = await loaded();
    const edit = screen.getByRole("button", { name: `Editar FAQ: ${first.question}` });
    await user.click(edit);
    const question = screen.getByRole("textbox", { name: "Pergunta" });
    await user.clear(question);
    await user.type(question, "Pergunta corrigida");
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(feedback.error).toHaveBeenCalledWith("Erro de edição simulado");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(question).toHaveValue("Pergunta corrigida");
    expect(screen.getByRole("textbox", { name: "Resposta" })).toHaveValue(first.answer);
    expect(question).toBeEnabled();
    api.update.mockResolvedValueOnce({ ...first, question: "Pergunta corrigida" });
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(api.update).toHaveBeenLastCalledWith(first.id, { question: "Pergunta corrigida", answer: first.answer });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Pergunta corrigida" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: second.question })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar FAQ: Pergunta corrigida" })).toHaveFocus();
  });

  it("mantém diálogo/conteúdo em falha de criação", async () => {
    api.create.mockRejectedValue(new Error("Erro de criação simulado"));
    const user = await loaded();
    await newForm(user);
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    expect(feedback.error).toHaveBeenCalledWith("Erro de criação simulado");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Pergunta" })).toHaveValue("Nova pergunta");
    expect(screen.getByRole("textbox", { name: "Resposta" })).toHaveValue("Nova resposta");
  });

  it("conserva switch/badge na recusa por limite e aplica somente o retorno confirmado", async () => {
    api.toggleChatbot.mockRejectedValueOnce(new Error("Limite de 4 FAQs no chatbot atingido"));
    const user = await loaded();
    const toggle = screen.getByRole("switch", { name: `Exibir no chatbot: ${first.question}` });
    await user.click(toggle);
    expect(toggle).not.toBeChecked();
    expect(feedback.error).toHaveBeenCalledWith("Limite de 4 FAQs no chatbot atingido");
    expect(within(toggle.closest("li")!).getByText("Oculta")).toBeInTheDocument();
    const request = deferred<Faq>();
    api.toggleChatbot.mockReturnValueOnce(request.promise);
    await user.click(toggle);
    expect(toggle).not.toBeChecked();
    await act(async () => request.resolve({ ...first, show_in_chatbot: true }));
    expect(toggle).toBeChecked();
    expect(within(toggle.closest("li")!).getByText("No Chatbot")).toBeInTheDocument();
    expect(api.toggleChatbot).toHaveBeenLastCalledWith(first.id);
  });

  it("exclui diretamente só após sucesso; falha conserva item e feedback", async () => {
    api.delete.mockRejectedValueOnce(new Error("Erro de exclusão simulado"));
    const user = await loaded();
    await user.click(screen.getByRole("button", { name: `Excluir FAQ: ${first.question}` }));
    expect(feedback.error).toHaveBeenCalledWith("Erro de exclusão simulado");
    expect(screen.getByRole("heading", { name: first.question })).toBeInTheDocument();
    const request = deferred<void>();
    api.delete.mockReturnValueOnce(request.promise);
    await user.click(screen.getByRole("button", { name: `Excluir FAQ: ${first.question}` }));
    expect(screen.getByRole("heading", { name: first.question })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await act(async () => request.resolve());
    expect(screen.queryByRole("heading", { name: first.question })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: second.question })).toBeInTheDocument();
    expect(api.delete).toHaveBeenLastCalledWith(first.id);
  });

  it("nomeia ações/campos e devolve foco à origem após Escape", async () => {
    const user = await loaded();
    const edit = screen.getByRole("button", { name: `Editar FAQ: ${second.question}` });
    edit.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog", { name: "Editar FAQ" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Pergunta" })).toHaveValue(second.question);
    expect(screen.getByRole("textbox", { name: "Resposta" })).toHaveValue(second.answer);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(edit).toHaveFocus());
  });
});

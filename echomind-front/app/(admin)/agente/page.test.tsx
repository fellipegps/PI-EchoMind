import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ getUser: vi.fn(), streamChat: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock("@/lib/supabase", () => ({ supabase: { auth: { getUser: mocks.getUser } } }));
vi.mock("@/lib/api", () => ({ streamChat: mocks.streamChat }));
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }));
import ChatbotTest from "./page";

describe("Agente administrativo — contrato DS-15", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocks.getUser.mockResolvedValue({ data: { user: { id: "authenticated-user-id" } } });
    mocks.streamChat.mockResolvedValue(undefined);
  });

  it("ignora entrada vazia e aguarda contexto autenticado inclusive por Enter", async () => {
    const user = userEvent.setup();
    let resolveUser!: (value: unknown) => void;
    mocks.getUser.mockReturnValue(new Promise(resolve => { resolveUser = resolve; }));
    render(<ChatbotTest />);
    const input = screen.getByLabelText("Mensagem para o agente");
    await user.type(input, "   {Enter}");
    await user.clear(input);
    await user.type(input, "Pergunta{Enter}");
    expect(mocks.streamChat).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Enviar mensagem" })).toBeDisabled();
    await act(async () => resolveUser({ data: { user: { id: "authenticated-user-id" } } }));
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(mocks.streamChat).not.toHaveBeenCalled();
    await user.keyboard("{Enter}");
    expect(mocks.streamChat).toHaveBeenCalledWith("Pergunta", "authenticated-user-id", expect.any(Function), expect.any(Function), expect.any(Function));
  });

  it("acumula tokens uma vez, ignora vazio, bloqueia envio pendente e libera ao concluir", async () => {
    const user = userEvent.setup();
    render(<ChatbotTest />);
    await user.type(screen.getByLabelText("Mensagem para o agente"), "  Olá  {Enter}");
    const [, , token, done] = mocks.streamChat.mock.calls[0];
    const log = screen.getByRole("log", { name: "Conversa de teste" });
    act(() => token(""));
    expect(within(log).queryByText("Agente:")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Aguardando a primeira resposta");
    expect(screen.getByLabelText("Mensagem para o agente")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Enviar mensagem" }));
    expect(mocks.streamChat).toHaveBeenCalledTimes(1);
    act(() => { token("Resposta"); token(" parcial\n"); token("final"); });
    expect(within(log).getAllByText("Agente:")).toHaveLength(1);
    expect(log).toHaveTextContent("Resposta parcial final");
    expect(screen.getByRole("status")).toHaveTextContent("Recebendo resposta");
    act(() => done());
    expect(screen.getByLabelText("Mensagem para o agente")).toBeEnabled();
  });

  it("mantém HTML/Markdown literais, conversa no resize e limpeza somente local", async () => {
    const user = userEvent.setup();
    render(<ChatbotTest />);
    await user.type(screen.getByLabelText("Mensagem para o agente"), "Teste{Enter}");
    const [, , token, done] = mocks.streamChat.mock.calls[0];
    const text = '<img src=x onerror=alert(1)>\n**texto** ' + "SemEspacos".repeat(100);
    act(() => { token(text); done(); });
    const log = screen.getByRole("log");
    expect(log.textContent).toContain(text);
    expect(log.querySelector("img, strong, script")).toBeNull();
    act(() => window.dispatchEvent(new Event("resize")));
    expect(log.textContent).toContain(text);
    await user.click(screen.getByRole("button", { name: "Limpar" }));
    expect(log).toHaveTextContent("Nenhuma mensagem enviada ainda.");
    expect(mocks.streamChat).toHaveBeenCalledTimes(1);
    expect(mocks.success).toHaveBeenCalledWith("Conversa reiniciada");
  });

  it("encerra loading no erro e comunica pelo toast, fora da conversa", async () => {
    const user = userEvent.setup();
    render(<ChatbotTest />);
    await user.type(screen.getByLabelText("Mensagem para o agente"), "Teste{Enter}");
    const error = mocks.streamChat.mock.calls[0][4];
    act(() => error(new Error("docker: indisponível")));
    expect(mocks.error).toHaveBeenCalledWith("A IA não retornou resposta. Verifique a conexão com o servidor.", { duration: 6000 });
    expect(screen.getByRole("log")).not.toHaveTextContent("docker");
    expect(screen.getByLabelText("Mensagem para o agente")).toBeEnabled();
    expect(screen.getByRole("status")).not.toHaveTextContent("Recebendo");
  });
});

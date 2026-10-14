import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AuthLayout from "./layout";
import LoginPage from "./login/page";
import RegisterPage from "./registrar-conta/page";
import ForgotPasswordPage from "./recuperar-senha/page";
import ResetPasswordPage from "./redefinir-senha/page";

const mocks = vi.hoisted(() => ({
  push: vi.fn(), login: vi.fn(), me: vi.fn(), register: vi.fn(),
  resetPassword: vi.fn(), updateUser: vi.fn(), success: vi.fn(), error: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/lib/api", () => ({ authApi: mocks }));
vi.mock("@/lib/supabase", () => ({ supabase: { auth: { updateUser: mocks.updateUser } } }));
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }));

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.updateUser.mockResolvedValue({ error: null });
});

const pages = [
  { Page: LoginPage, title: "Entrar no EchoMind", fields: ["Email", "Senha"], links: [["Criar conta", "/registrar-conta"], ["Esqueci minha senha", "/recuperar-senha"]] },
  { Page: RegisterPage, title: "Criar Conta", fields: ["Nome da Empresa", "Seu Nome", "Email", "Senha"], links: [["Entrar", "/login"]] },
  { Page: ForgotPasswordPage, title: "Recuperar Senha", fields: ["Email"], links: [["Voltar para o login", "/login"]] },
  { Page: ResetPasswordPage, title: "Redefinir senha", fields: ["Nova senha", "Confirmar senha"], links: [["Voltar para o login", "/login"]] },
];

describe.each(pages)("DS-02 composição: $title", ({ Page, title, fields, links }) => {
  it("mantém uma região identificada, campos obrigatórios e destinos reais", () => {
    render(<AuthLayout><Page /></AuthLayout>);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: title })).toBeInTheDocument();
    expect(screen.getByText("EchoMind", { exact: true })).toBeInTheDocument();
    fields.forEach((field) => expect(screen.getByLabelText(field, { exact: true })).toBeRequired());
    links.forEach(([name, href]) => expect(screen.getByRole("link", { name })).toHaveAttribute("href", href));
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("percorre os campos, envio e links na ordem de teclado", async () => {
    const user = userEvent.setup();
    render(<AuthLayout><Page /></AuthLayout>);
    for (const field of fields) {
      await user.tab();
      expect(screen.getByLabelText(field, { exact: true })).toHaveFocus();
    }
    await user.tab();
    expect(screen.getByRole("button")).toHaveFocus();
    for (const [name] of links) {
      await user.tab();
      expect(screen.getByRole("link", { name })).toHaveFocus();
    }
  });
});

describe("DS-02 login", () => {
  async function fillLogin() {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText("Email"), "auth@example.test");
    await user.type(screen.getByLabelText("Senha"), "teste-local");
    return user;
  }

  it("aguarda login, depois usuário, e só então segue ao dashboard", async () => {
    const login = deferred();
    const me = deferred();
    mocks.login.mockReturnValue(login.promise);
    mocks.me.mockReturnValue(me.promise);
    const user = await fillLogin();
    const submit = screen.getByRole("button", { name: "Entrar" });
    await user.click(submit);
    expect(mocks.login).toHaveBeenCalledWith("auth@example.test", "teste-local");
    expect(submit).toBeDisabled();
    expect(submit).toHaveAttribute("aria-busy", "true");
    expect(mocks.me).not.toHaveBeenCalled();
    await act(async () => login.resolve());
    expect(mocks.me).toHaveBeenCalledOnce();
    expect(mocks.push).not.toHaveBeenCalled();
    await act(async () => me.resolve());
    expect(mocks.success).toHaveBeenCalledWith("Login realizado com sucesso!");
    expect(mocks.push).toHaveBeenCalledWith("/dashboard");
    expect(submit).toBeEnabled();
  });

  it.each(["login", "me"] as const)("falha em %s informa erro, libera tentativa e não redireciona", async (stage) => {
    mocks[stage].mockRejectedValueOnce(new Error("Falha simulada de autenticação"));
    const user = await fillLogin();
    const submit = screen.getByRole("button", { name: "Entrar" });
    await user.click(submit);
    await waitFor(() => expect(mocks.error).toHaveBeenCalledWith("Falha simulada de autenticação"));
    expect(submit).toBeEnabled();
    expect(mocks.push).not.toHaveBeenCalled();
    if (stage === "login") expect(mocks.me).not.toHaveBeenCalled();
    await user.click(submit);
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/dashboard"));
  });

  it("preserva tipos, autocomplete e validação nativa antes do envio", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email");
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText("Senha")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("Senha")).toHaveAttribute("autocomplete", "current-password");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(mocks.login).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Email"), "email-invalido");
    await user.type(screen.getByLabelText("Senha"), "teste-local");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(mocks.login).not.toHaveBeenCalled();
  });
});

describe("DS-02 cadastro", () => {
  async function fillRegister(password: string) {
    const user = userEvent.setup();
    render(<RegisterPage />);
    await user.type(screen.getByLabelText("Nome da Empresa"), "Instituição de teste");
    await user.type(screen.getByLabelText("Seu Nome"), "Pessoa de teste");
    await user.type(screen.getByLabelText("Email"), "auth@example.test");
    await user.type(screen.getByLabelText("Senha"), password);
    return user;
  }

  it("impede senha curta sem alterar o mínimo de seis caracteres", async () => {
    const user = await fillRegister("12345");
    await user.click(screen.getByRole("button", { name: "Criar Conta" }));
    expect(mocks.error).toHaveBeenCalledWith("A senha deve ter pelo menos 6 caracteres");
    expect(mocks.register).not.toHaveBeenCalled();
  });

  it("mantém quatro valores, bloqueia durante envio e orienta confirmação antes do login", async () => {
    const request = deferred();
    mocks.register.mockReturnValue(request.promise);
    const user = await fillRegister("123456");
    const submit = screen.getByRole("button", { name: "Criar Conta" });
    await user.click(submit);
    expect(submit).toBeDisabled();
    expect(submit).toHaveAttribute("aria-busy", "true");
    expect(mocks.register).toHaveBeenCalledWith("auth@example.test", "123456", { fullName: "Pessoa de teste", companyName: "Instituição de teste" });
    expect(mocks.push).not.toHaveBeenCalled();
    await act(async () => request.resolve());
    expect(mocks.success).toHaveBeenCalledWith("Cadastro realizado! Verifique seu email para confirmar a conta.");
    expect(mocks.push).toHaveBeenCalledWith("/login");
    expect(submit).toBeEnabled();
  });

  it("libera nova tentativa após erro, sem navegação indevida", async () => {
    mocks.register.mockRejectedValueOnce(new Error("Cadastro indisponível"));
    const user = await fillRegister("123456");
    const submit = screen.getByRole("button", { name: "Criar Conta" });
    await user.click(submit);
    await waitFor(() => expect(mocks.error).toHaveBeenCalledWith("Cadastro indisponível"));
    expect(submit).toBeEnabled();
    expect(mocks.push).not.toHaveBeenCalled();
    await user.click(submit);
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/login"));
  });
});

describe("DS-02 recuperação", () => {
  it("exibe carregamento, permite repetir após falha e anuncia confirmação com retorno", async () => {
    const request = deferred();
    mocks.resetPassword.mockReturnValueOnce(request.promise);
    const user = userEvent.setup();
    render(<ForgotPasswordPage />);
    await user.type(screen.getByLabelText("Email"), "auth@example.test");
    const submit = screen.getByRole("button", { name: "Enviar Link" });
    await user.click(submit);
    expect(mocks.resetPassword).toHaveBeenCalledWith("auth@example.test");
    expect(submit).toBeDisabled();
    expect(submit).toHaveAttribute("aria-busy", "true");
    await act(async () => request.reject(new Error("Envio indisponível")));
    expect(mocks.error).toHaveBeenCalledWith("Envio indisponível");
    expect(submit).toBeEnabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await user.click(submit);
    expect(await screen.findByRole("status")).toHaveTextContent("Email enviado com sucesso! Verifique sua caixa de entrada para continuar.");
    expect(mocks.success).toHaveBeenCalledWith("Email de recuperação enviado!");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voltar para o login" })).toHaveAttribute("href", "/login");
  });
});

describe("DS-02 redefinição", () => {
  it.each([
    ["12345", "12345", "A senha deve ter pelo menos 6 caracteres"],
    ["123456", "654321", "As senhas nao conferem"],
  ])("valida as senhas antes de qualquer atualização (%s / %s)", async (password, confirmation, message) => {
    const user = userEvent.setup();
    render(<ResetPasswordPage />);
    await user.type(screen.getByLabelText("Nova senha"), password);
    await user.type(screen.getByLabelText("Confirmar senha"), confirmation);
    await user.click(screen.getByRole("button", { name: "Atualizar senha" }));
    expect(mocks.error).toHaveBeenCalledWith(message);
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Nova senha")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByLabelText("Confirmar senha")).toHaveAttribute("autocomplete", "new-password");
  });

  it("mantém contrato, carregamento, erro recuperável e confirmação de atualização simulada", async () => {
    const request = deferred<{ error: { message: string } | null }>();
    mocks.updateUser.mockReturnValueOnce(request.promise);
    const user = userEvent.setup();
    render(<ResetPasswordPage />);
    await user.type(screen.getByLabelText("Nova senha"), "teste-local");
    await user.type(screen.getByLabelText("Confirmar senha"), "teste-local");
    const submit = screen.getByRole("button", { name: "Atualizar senha" });
    await user.click(submit);
    expect(mocks.updateUser).toHaveBeenCalledWith({ password: "teste-local" });
    expect(submit).toBeDisabled();
    expect(submit).toHaveAttribute("aria-busy", "true");
    await act(async () => request.resolve({ error: { message: "Link de teste expirado" } }));
    expect(mocks.error).toHaveBeenCalledWith("Link de teste expirado");
    expect(submit).toBeEnabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await user.click(submit);
    expect(await screen.findByRole("status")).toHaveTextContent("Sua senha foi atualizada. Voce ja pode acessar sua conta.");
    expect(mocks.success).toHaveBeenCalledWith("Senha atualizada com sucesso!");
    expect(screen.queryByLabelText("Nova senha")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voltar para o login" })).toHaveAttribute("href", "/login");
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ signUp: vi.fn() }));
vi.mock("./supabase", () => ({ supabase: { auth: { signUp: mocks.signUp } } }));

import { authApi } from "./api";

beforeEach(() => vi.resetAllMocks());

describe("cadastro e confirmação do Supabase", () => {
  it.each([
    { session: null, requiresEmailConfirmation: true },
    { session: {}, requiresEmailConfirmation: false },
  ])("informa confirmação pendente=$requiresEmailConfirmation a partir da sessão retornada", async ({ session, requiresEmailConfirmation }) => {
    mocks.signUp.mockResolvedValue({
      data: { user: { email: "auth@example.test" }, session }, error: null,
    });
    await expect(authApi.register("auth@example.test", "synthetic-password", {
      fullName: "Pessoa de teste", companyName: "Instituição de teste",
    })).resolves.toEqual({ email: "auth@example.test", requiresEmailConfirmation });
    expect(mocks.signUp).toHaveBeenCalledWith({
      email: "auth@example.test", password: "synthetic-password",
      options: { data: { full_name: "Pessoa de teste", company_name: "Instituição de teste" } },
    });
  });

  it("preserva erros do provedor sem anunciar uma conta criada", async () => {
    mocks.signUp.mockResolvedValue({ data: { user: null, session: null }, error: { message: "Cadastro indisponível" } });
    await expect(authApi.register("auth@example.test", "synthetic-password")).rejects.toThrow("Cadastro indisponível");
  });
});

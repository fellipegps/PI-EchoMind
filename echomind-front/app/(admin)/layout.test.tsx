import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
import { SessionExpiredError } from "@/lib/authenticated-fetch";
import AppLayout from "./layout";

const mocks = vi.hoisted(() => ({
  onChange: vi.fn(),
  unsubscribe: vi.fn(),
  me: vi.fn(),
  replace: vi.fn(),
}));
const router = { replace: mocks.replace };
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/supabase", () => ({ supabase: { auth: { onAuthStateChange: mocks.onChange } } }));
vi.mock("@/lib/api", () => ({ authApi: { me: mocks.me } }));
vi.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SidebarTrigger: () => <button>Alternar navegação</button>,
}));
vi.mock("@/components/app-sidebar", () => ({ AppSidebar: () => <nav>Navegação de teste</nav> }));
vi.mock("@/components/mode-toggle", () => ({ ModeToggle: () => <button>Alternar tema</button> }));

function PageState() {
  const [value, setValue] = useState(0);
  return <button onClick={() => setValue((count) => count + 1)}>Conteúdo protegido {value}</button>;
}

function emitAuthEvent(event: AuthChangeEvent, session: Partial<Session> | null) {
  act(() => mocks.onChange.mock.calls[0][0](event, session));
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.me.mockResolvedValue({ id: "fixture" });
  mocks.onChange.mockReturnValue({ data: { subscription: { unsubscribe: mocks.unsubscribe } } });
});

describe("Estrutura administrativa e contrato de sessão", () => {
  it("aguarda autorização e conserva o estado da página durante a renovação", async () => {
    let resolveMe!: (user: { id: string }) => void;
    mocks.me.mockImplementationOnce(() => new Promise((resolve) => { resolveMe = resolve; }));
    render(<AppLayout><PageState /></AppLayout>);
    expect(screen.queryByText(/Conteúdo protegido/)).not.toBeInTheDocument();

    await act(async () => resolveMe({ id: "fixture" }));
    await userEvent.click(await screen.findByRole("button", { name: "Conteúdo protegido 0" }));
    emitAuthEvent("TOKEN_REFRESHED", { access_token: "renovado" });

    expect(screen.getByRole("button", { name: "Conteúdo protegido 1" })).toBeInTheDocument();
    expect(mocks.me).toHaveBeenCalledOnce();
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("redireciona quando a verificação confirma ausência de sessão", async () => {
    mocks.me.mockRejectedValueOnce(new SessionExpiredError());
    render(<AppLayout><PageState /></AppLayout>);

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText(/Conteúdo protegido/)).not.toBeInTheDocument();
  });

  it("permite repetir a validação após uma falha temporária sem voltar ao login", async () => {
    mocks.me.mockRejectedValueOnce(new Error("Servidor indisponível"));
    render(<AppLayout><PageState /></AppLayout>);
    emitAuthEvent("INITIAL_SESSION", null);

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível validar sua sessão");
    expect(screen.queryByText(/Conteúdo protegido/)).not.toBeInTheDocument();
    expect(mocks.replace).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByRole("button", { name: "Conteúdo protegido 0" })).toBeInTheDocument();
    expect(mocks.me).toHaveBeenCalledTimes(2);
  });

  it("esconde o conteúdo no logout e libera a assinatura ao desmontar", async () => {
    const { unmount } = render(<AppLayout><PageState /></AppLayout>);
    await screen.findByRole("button", { name: "Conteúdo protegido 0" });

    emitAuthEvent("SIGNED_OUT", null);

    expect(mocks.replace).toHaveBeenCalledWith("/login");
    expect(screen.queryByText(/Conteúdo protegido/)).not.toBeInTheDocument();
    unmount();
    expect(mocks.unsubscribe).toHaveBeenCalledOnce();
  });
});

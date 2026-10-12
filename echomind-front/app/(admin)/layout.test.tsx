import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ getSession: vi.fn(), onChange: vi.fn(), unsubscribe: vi.fn(), me: vi.fn(), set: vi.fn(), clear: vi.fn(), replace: vi.fn() }));
const router = { replace: mocks.replace };
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/supabase", () => ({ supabase: { auth: { getSession: mocks.getSession, onAuthStateChange: mocks.onChange } } }));
vi.mock("@/lib/api", () => ({ authApi: { me: mocks.me }, tokenStore: { set: mocks.set, clear: mocks.clear } }));
vi.mock("@/components/ui/sidebar", () => ({ SidebarProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>, SidebarTrigger: () => <button>Alternar navegação</button> }));
vi.mock("@/components/app-sidebar", () => ({ AppSidebar: () => <nav>Navegação de teste</nav> }));
vi.mock("@/components/mode-toggle", () => ({ ModeToggle: () => <button>Alternar tema</button> }));
import AppLayout from "./layout";
function PageState() { const [value,setValue] = useState(0);return <button onClick={() => setValue(v => v + 1)}>Conteúdo protegido {value}</button>; }
beforeEach(() => { vi.clearAllMocks();mocks.getSession.mockResolvedValue({ data: { session: { access_token: "fixture-token" } } });mocks.me.mockResolvedValue({ id: "fixture" });mocks.onChange.mockReturnValue({ data: { subscription: { unsubscribe: mocks.unsubscribe } } }); });
describe("Estrutura administrativa e contrato de sessão", () => {
  it("aguarda autorização, sincroniza token e preserva o estado da página ao renderizar novamente", async () => {
    let resolveMe!: () => void;mocks.me.mockImplementation(() => new Promise<void>(resolve => { resolveMe = resolve; }));
    const { rerender } = render(<AppLayout><PageState /></AppLayout>);
    expect(screen.queryByText(/Conteúdo protegido/)).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.me).toHaveBeenCalledOnce());
    expect(mocks.set).toHaveBeenCalledWith("fixture-token");
    await act(async () => resolveMe());
    await userEvent.click(await screen.findByRole("button", { name: "Conteúdo protegido 0" }));
    rerender(<AppLayout><PageState /></AppLayout>);
    expect(screen.getByRole("button", { name: "Conteúdo protegido 1" })).toBeInTheDocument();expect(mocks.getSession).toHaveBeenCalledOnce();
  });
  it("redireciona sessão ausente sem mostrar o conteúdo", async () => {
    mocks.getSession.mockResolvedValue({ data: { session: null } });render(<AppLayout><PageState /></AppLayout>);
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/login"));expect(mocks.clear).toHaveBeenCalledOnce();expect(mocks.me).not.toHaveBeenCalled();expect(screen.queryByText(/Conteúdo protegido/)).not.toBeInTheDocument();
  });
  it("redireciona sessão rejeitada pela API sem mostrar o conteúdo", async () => {
    mocks.me.mockRejectedValue(new Error("Sessão de teste rejeitada"));render(<AppLayout><PageState /></AppLayout>);
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/login"));expect(mocks.clear).toHaveBeenCalledOnce();expect(screen.queryByText(/Conteúdo protegido/)).not.toBeInTheDocument();
  });
  it("sincroniza mudança de sessão e libera a assinatura ao desmontar", async () => {
    const { unmount } = render(<AppLayout><PageState /></AppLayout>);await screen.findByRole("button", { name: "Conteúdo protegido 0" });
    const callback = mocks.onChange.mock.calls[0][0];await act(async () => callback("TOKEN_REFRESHED", { access_token: "updated-fixture-token" }));expect(mocks.set).toHaveBeenLastCalledWith("updated-fixture-token");expect(mocks.me).toHaveBeenCalledTimes(2);
    await act(async () => callback("SIGNED_OUT", null));expect(mocks.replace).toHaveBeenCalledWith("/login");expect(mocks.clear).toHaveBeenCalledOnce();unmount();expect(mocks.unsubscribe).toHaveBeenCalledOnce();
  });
  it("limpa assinatura mesmo quando desmonta antes da verificação", async () => {
    let resolveMe!: () => void;mocks.me.mockImplementation(() => new Promise<void>(resolve => { resolveMe = resolve; }));const { unmount }=render(<AppLayout><PageState /></AppLayout>);await waitFor(() => expect(mocks.me).toHaveBeenCalledOnce());unmount();await act(async () => resolveMe());expect(mocks.unsubscribe).toHaveBeenCalledOnce();
  });
});

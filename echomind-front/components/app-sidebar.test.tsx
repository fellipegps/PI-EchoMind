import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
const state = vi.hoisted(() => ({ pathname: "/dashboard", mobile: false, replace: vi.fn(), logout: vi.fn() }));
const router={replace:state.replace};
vi.mock("next/navigation", () => ({ usePathname: () => state.pathname, useRouter: () => router }));
vi.mock("next/link", () => ({ default: ({ onClick, ...props }: ComponentProps<"a">) => <a {...props} onClick={event => { event.preventDefault();onClick?.(event); }} /> }));
vi.mock("@/hooks/use-mobile", () => ({ useIsMobile: () => state.mobile }));
vi.mock("@/lib/api", () => ({ authApi: { logout: state.logout } }));
import { AppSidebar } from "./app-sidebar";
import { SidebarProvider, SidebarTrigger } from "./ui/sidebar";
const routes=["/dashboard","/base-de-conhecimento","/campi","/locais","/eventos","/nao-respondidas","/agente","/configuracoes"];
beforeEach(() => {vi.clearAllMocks();state.mobile=false;state.pathname="/dashboard";state.logout.mockResolvedValue(undefined);});
describe("Navegação administrativa", () => {
 it("preserva os oito destinos e identifica somente a rota atual", () => {
  const {rerender}=render(<SidebarProvider><AppSidebar /></SidebarProvider>);
  for(const route of routes){state.pathname=route;rerender(<SidebarProvider><AppSidebar /></SidebarProvider>);const links=screen.getAllByRole("link");expect(links.map(l=>l.getAttribute("href")).sort()).toEqual([...routes].sort());expect(links.filter(l=>l.getAttribute("aria-current")==="page").map(l=>l.getAttribute("href"))).toEqual([route]);}
 });
 it("abre o menu móvel, alcança seus destinos e fecha após seleção ou Escape",async()=>{
  state.mobile=true;const user=userEvent.setup();render(<SidebarProvider><SidebarTrigger /><AppSidebar /></SidebarProvider>);await user.click(screen.getByRole("button",{name:"Alternar navegação"}));expect(await screen.findByRole("dialog",{name:"Navegação administrativa"})).toBeInTheDocument();expect(screen.getAllByRole("link")).toHaveLength(8);await user.click(screen.getByRole("link",{name:"Eventos"}));await waitFor(()=>expect(screen.queryByRole("dialog")).not.toBeInTheDocument());await user.click(screen.getByRole("button",{name:"Alternar navegação"}));await user.keyboard("{Escape}");await waitFor(()=>expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
 });
 it("aguarda a saída existente e redireciona ao login",async()=>{render(<SidebarProvider><AppSidebar /></SidebarProvider>);await userEvent.click(screen.getByRole("button",{name:"Sair"}));await waitFor(()=>expect(state.replace).toHaveBeenCalledWith("/login"));expect(state.logout).toHaveBeenCalledOnce();});
});

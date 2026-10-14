"use client";

import { LayoutDashboard, HelpCircle, Bot, Settings, LogOut, Database, MapPinned, CalendarDays, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { EchoMindBrand } from "@/components/echomind-brand";
import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/api";

const menuGroups = [
  { title: "Geral", items: [
    { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
    { title: "Base de Conhecimento", url: "/base-de-conhecimento", icon: Database },
    { title: "Não Respondidas", url: "/nao-respondidas", icon: HelpCircle },
    { title: "Agente (Chatbot)", url: "/agente", icon: Bot },
  ] },
  { title: "Campus e eventos", items: [
    { title: "Mapa dos Campi", url: "/campi", icon: MapPinned },
    { title: "Eventos", url: "/eventos", icon: CalendarDays },
  ] },
  { title: "Sistema", items: [
    { title: "Configurações", url: "/configuracoes", icon: Settings },
  ] },
];

const menuControl = "h-auto min-h-11 gap-3 px-3 py-3 text-sm leading-5 focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar scroll-my-2 [&>svg]:size-5 [&>span:last-child]:overflow-visible [&>span:last-child]:whitespace-normal motion-reduce:transition-none";

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isMobile, setOpenMobile } = useSidebar();

  const handleLogout = async () => {
    await authApi.logout();
    router.replace("/login");
  };

  return (
    <Sidebar className="border-sidebar-border">
      <SidebarHeader className="gap-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <EchoMindBrand />
          {isMobile && <Button type="button" variant="ghost" size="icon" aria-label="Fechar navegação" onClick={() => setOpenMobile(false)}><X aria-hidden="true" /></Button>}
        </div>
        <p className="text-xs leading-4 text-muted-foreground">Painel administrativo</p>
      </SidebarHeader>
      <SidebarSeparator />
      <SidebarContent className="gap-4 px-2 py-4">
        <nav aria-label="Navegação administrativa" className="space-y-4">
          {menuGroups.map((group) => <SidebarGroup key={group.title} className="p-0">
            <SidebarGroupLabel className="px-3 text-xs leading-4 font-medium tracking-wider text-muted-foreground uppercase">{group.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => {
                  const isActive = pathname === item.url;
                  return <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton asChild isActive={isActive} className={menuControl}>
                      <Link href={item.url} aria-current={isActive ? "page" : undefined} onClick={() => { if (isMobile) setOpenMobile(false); }}>
                        <item.icon aria-hidden="true" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>;
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>)}
        </nav>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={handleLogout} className={`${menuControl} text-destructive hover:bg-sidebar hover:text-destructive`}>
              <LogOut aria-hidden="true" />
              <span>Sair</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { ModeToggle } from "@/components/mode-toggle";
import { authApi } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    // Verifica se há token no localStorage.
    // Se não houver, redireciona para o login antes de renderizar qualquer
    // página do painel admin.
    if (!authApi.isAuthenticated()) {
      router.replace("/login");
    }
  }, [router]);

  // Não renderiza nada até a verificação de auth ter ocorrido no client
  if (typeof window !== "undefined" && !authApi.isAuthenticated()) {
    return null;
  }

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <AppSidebar />
        <main className="flex-1 flex flex-col">
          <div className="sticky top-0 z-10 flex items-center gap-2 p-2 border-b bg-background">
            <SidebarTrigger />
            <div className="ml-auto"><ModeToggle /></div>
          </div>
          {children}
        </main>
      </div>
    </SidebarProvider>
  );
}

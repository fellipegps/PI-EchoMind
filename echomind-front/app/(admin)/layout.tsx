"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { ModeToggle } from "@/components/mode-toggle";
import { authApi, tokenStore } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    let mounted = true;

    const syncSession = async (accessToken?: string) => {
      if (!accessToken) {
        tokenStore.clear();
        router.replace("/login");
        return;
      }

      tokenStore.set(accessToken);
      try {
        await authApi.me();
        if (mounted) setCheckingAuth(false);
      } catch {
        tokenStore.clear();
        router.replace("/login");
      }
    };

    supabase.auth.getSession().then(({ data }) => {
      syncSession(data.session?.access_token);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        syncSession(session?.access_token);
      }
    );

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [router]);

  if (checkingAuth) {
    return null;
  }

  return (
    <SidebarProvider>
      <div className="flex min-h-svh w-full min-w-0">
        <AppSidebar />
        <main className="flex min-w-0 flex-1 flex-col bg-background text-foreground">
          <div className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-card px-4 md:px-6" aria-label="Cabeçalho administrativo">
            <SidebarTrigger className="size-11 shrink-0" aria-label="Alternar navegação" />
            <span className="min-w-0 text-sm leading-5 text-muted-foreground">Painel administrativo</span>
            <div className="ml-auto"><ModeToggle /></div>
          </div>
          {children}
        </main>
      </div>
    </SidebarProvider>
  );
}

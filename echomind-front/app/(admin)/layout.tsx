"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { ModeToggle } from "@/components/mode-toggle";
import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/api";
import { SessionExpiredError } from "@/lib/authenticated-fetch";
import { supabase } from "@/lib/supabase";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [authStatus, setAuthStatus] = useState<"checking" | "error" | "ready">("checking");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    let userId: string | undefined;

    const redirectToLogin = () => {
      active = false;
      setAuthStatus("checking");
      router.replace("/login");
    };

    const validateAgain = () => {
      active = false;
      setAuthStatus("checking");
      setAttempt((value) => value + 1);
    };

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (!active) return;
        if (event === "SIGNED_OUT") redirectToLogin();
        if ((event === "SIGNED_IN" || event === "INITIAL_SESSION") && session) {
          if (userId && session.user.id !== userId) validateAgain();
          userId = session.user.id;
        }
      }
    );

    authApi.me().then((user) => {
      if (!active) return;
      if (userId && userId !== user.id) {
        validateAgain();
        return;
      }
      userId = user.id;
      setAuthStatus("ready");
    }).catch((error: unknown) => {
      if (!active) return;
      if (error instanceof SessionExpiredError) redirectToLogin();
      else setAuthStatus("error");
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [attempt, router]);

  if (authStatus === "checking") return null;

  if (authStatus === "error") {
    return (
      <main className="grid min-h-svh place-items-center p-6">
        <div className="space-y-4 text-center">
          <p role="alert">Não foi possível validar sua sessão no painel.</p>
          <Button type="button" onClick={() => {
            setAuthStatus("checking");
            setAttempt((value) => value + 1);
          }}>Tentar novamente</Button>
        </div>
      </main>
    );
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

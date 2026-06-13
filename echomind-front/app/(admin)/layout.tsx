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

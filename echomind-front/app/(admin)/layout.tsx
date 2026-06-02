"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { ModeToggle } from "@/components/mode-toggle";
import { authApi } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    if (!authApi.isAuthenticated()) {
      router.replace("/login");
      return;
    }

    authApi.me()
      .then(() => setCheckingAuth(false))
      .catch(() => router.replace("/login"));
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

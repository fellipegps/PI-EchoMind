import type { ReactNode } from "react";
import { Bot, CalendarDays, MapPin } from "lucide-react";
import { EchoMindBrand } from "@/components/echomind-brand";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { id: "chat", label: "Chat", icon: Bot },
  { id: "eventos", label: "Eventos", icon: CalendarDays },
  { id: "locais", label: "Locais", icon: MapPin },
] as const;

export type PortalTabId = (typeof NAV_ITEMS)[number]["id"];

export function PortalShell({ activeTab, onTabChange, companyName, children }: {
  activeTab: PortalTabId;
  onTabChange: (tab: PortalTabId) => void;
  companyName: string;
  children: ReactNode;
}) {
  return (
    <div data-slot="portal-shell" className="min-h-svh bg-background pb-[calc(80px+env(safe-area-inset-bottom))] text-foreground lg:pb-0">
      <nav aria-label="Navegação principal" className="fixed inset-x-0 bottom-0 z-30 border-t border-sidebar-border bg-sidebar pb-[env(safe-area-inset-bottom)] text-sidebar-foreground lg:inset-y-0 lg:right-auto lg:w-56 lg:border-t-0 lg:border-r">
        <div className="hidden border-b border-sidebar-border px-6 pb-6 pt-[calc(1.5rem+env(safe-area-inset-top))] lg:block">
          <EchoMindBrand className="text-xl leading-7" />
        </div>
        <div className="flex gap-2 py-2 pl-[max(0.5rem,env(safe-area-inset-left))] pr-[max(0.5rem,env(safe-area-inset-right))] lg:flex-col lg:p-4">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <Button
              key={id}
              type="button"
              variant="ghost"
              aria-current={activeTab === id ? "page" : undefined}
              onClick={() => onTabChange(id)}
              className="h-auto min-h-14 min-w-0 flex-1 flex-col gap-1 rounded-sm px-3 py-2 text-sm leading-5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground aria-[current=page]:bg-sidebar-accent aria-[current=page]:font-semibold aria-[current=page]:text-sidebar-accent-foreground lg:min-h-12 lg:flex-none lg:flex-row lg:justify-start lg:gap-3 lg:px-4 lg:py-3"
            >
              <Icon aria-hidden="true" className="size-5" />
              <span>{label}</span>
            </Button>
          ))}
        </div>
      </nav>

      <div className="min-w-0 lg:ml-56">
        <header className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-4 border-b border-border bg-card pb-4 pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))] pt-[calc(1rem+env(safe-area-inset-top))] sm:pl-[max(1.5rem,env(safe-area-inset-left))] sm:pr-[max(1.5rem,env(safe-area-inset-right))]">
          <EchoMindBrand className="text-lg leading-6 lg:hidden" />
          <div className="col-span-2 min-w-0 space-y-1 lg:col-span-1">
            <p className="text-xs leading-4 font-medium text-muted-foreground">Portal do estudante</p>
            <h1 className="text-2xl leading-8 font-semibold tracking-tight [overflow-wrap:anywhere]">{companyName}</h1>
          </div>
          <span className="col-start-2 row-start-1 inline-flex items-center gap-2 rounded-full border border-border bg-muted px-3 py-1 text-xs leading-4 font-medium text-success">
            <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-success" />Assistente online
          </span>
        </header>

        <main className={cn("grid min-w-0 gap-6 py-6 pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))] sm:pl-[max(1.5rem,env(safe-area-inset-left))] sm:pr-[max(1.5rem,env(safe-area-inset-right))]", activeTab === "chat" && "xl:grid-cols-[minmax(0,1fr)_288px]")}>
          <div className="min-w-0">{children}</div>
          {/* DS-03 reserves this space. Real auxiliary content belongs to DS-04. */}
          {activeTab === "chat" ? <div data-slot="portal-auxiliary" aria-hidden="true" className="hidden min-w-0 xl:block" /> : null}
        </main>
      </div>
    </div>
  );
}

export function PortalSectionHeading({ id, eyebrow, title, description, icon }: {
  id: string;
  eyebrow: string;
  title: string;
  description?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-center gap-3 text-foreground">
      {icon ? <span aria-hidden="true" className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent text-primary">{icon}</span> : null}
      <div className="min-w-0 space-y-1">
        <p className="text-sm leading-5 font-medium text-primary">{eyebrow}</p>
        <h2 id={id} className="text-2xl leading-8 font-semibold tracking-tight">{title}</h2>
        {description ? <p className="text-base leading-6 text-muted-foreground">{description}</p> : null}
      </div>
    </div>
  );
}

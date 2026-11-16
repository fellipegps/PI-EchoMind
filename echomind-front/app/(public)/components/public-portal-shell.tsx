import { useState, useSyncExternalStore, type ReactNode, type RefCallback } from "react";
import Link from "next/link";
import { Bot, CalendarDays, ChevronDown, MapPin } from "lucide-react";
import { EchoMindBrand } from "@/components/echomind-brand";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import styles from "./public-portal.module.css";

const NAV_ITEMS = [
  { id: "chat", label: "Chat", icon: Bot },
  { id: "eventos", label: "Eventos", icon: CalendarDays },
  { id: "locais", label: "Locais", icon: MapPin },
] as const;

export type PortalTabId = (typeof NAV_ITEMS)[number]["id"];

const DESKTOP_QUERY = "(min-width: 64rem)";

function subscribeToDesktopLayout(onChange: () => void) {
  if (typeof window.matchMedia !== "function") return () => {};
  const media = window.matchMedia(DESKTOP_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

function isDesktopLayout() {
  return typeof window.matchMedia !== "function" || window.matchMedia(DESKTOP_QUERY).matches;
}

export function PortalShell({ activeTab, onTabChange, companyName, children, auxiliary, placesDirectoryRef, privacyHref = "/privacidade" }: {
  activeTab: PortalTabId;
  onTabChange: (tab: PortalTabId) => void;
  companyName: string;
  children: ReactNode;
  auxiliary?: ReactNode;
  placesDirectoryRef: RefCallback<HTMLDivElement>;
  privacyHref?: string;
}) {
  const [placesExpanded, setPlacesExpanded] = useState(false);
  const isDesktop = useSyncExternalStore(subscribeToDesktopLayout, isDesktopLayout, () => true);
  const isPlacesTab = activeTab === "locais";
  const showDirectory = isPlacesTab && placesExpanded;

  return (
    <div data-slot="portal-shell" className={cn("min-h-svh bg-background pb-[calc(80px+env(safe-area-inset-bottom))] text-foreground lg:pb-0", isPlacesTab && styles.mapLayout)}>
      <nav aria-label="Navegação principal" className={cn("fixed inset-x-0 bottom-0 z-30 border-t border-sidebar-border bg-sidebar pb-[env(safe-area-inset-bottom)] text-sidebar-foreground lg:inset-y-0 lg:right-auto lg:overflow-y-auto lg:border-t-0 lg:border-r",
        isPlacesTab ? "lg:static lg:min-h-0 lg:overscroll-contain" : "lg:w-56")}>
        <div className="hidden border-b border-sidebar-border px-6 pb-6 pt-[calc(1.5rem+env(safe-area-inset-top))] lg:block">
          <EchoMindBrand className="text-xl leading-7" />
        </div>
        <div className="flex gap-2 py-2 pl-[max(0.5rem,env(safe-area-inset-left))] pr-[max(0.5rem,env(safe-area-inset-right))] lg:flex-col lg:p-4">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <div key={id} className="min-w-0 flex-1 lg:flex-none">
              <Button
                type="button"
                variant="ghost"
                aria-current={activeTab === id ? "page" : undefined}
                aria-expanded={id === "locais" && isDesktop ? showDirectory : undefined}
                aria-controls={id === "locais" && isDesktop ? "portal-campus-directory" : undefined}
                onClick={() => {
                  if (id === "locais" && isDesktop) setPlacesExpanded(!showDirectory);
                  onTabChange(id);
                }}
                className="h-auto min-h-14 w-full min-w-0 flex-col gap-1 rounded-sm px-3 py-2 text-sm leading-5 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground aria-[current=page]:bg-sidebar-accent aria-[current=page]:font-semibold aria-[current=page]:text-sidebar-accent-foreground lg:min-h-12 lg:flex-row lg:justify-start lg:gap-3 lg:px-4 lg:py-3"
              >
                <Icon aria-hidden="true" className="size-5" />
                <span className="inline-flex items-center gap-1 lg:flex-1">{label}
                  {id === "locais" && <ChevronDown aria-hidden="true" className={cn("ml-auto hidden size-4 transition-transform motion-reduce:transition-none lg:block", showDirectory && "rotate-180")} />}
                </span>
              </Button>
              {id === "locais" && isDesktop && <div id="portal-campus-directory" ref={placesDirectoryRef}
                hidden={!showDirectory} className="mt-2 max-lg:hidden" />}
            </div>
          ))}
        </div>
      </nav>

      <div className={cn("min-w-0", isPlacesTab ? styles.mapContent : "lg:ml-56")}>
        <header className={cn("grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-4 border-b border-border bg-card pb-4 pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))] pt-[calc(1rem+env(safe-area-inset-top))] sm:pl-[max(1.5rem,env(safe-area-inset-left))] sm:pr-[max(1.5rem,env(safe-area-inset-right))]", isPlacesTab && "max-lg:gap-y-2 max-lg:pb-2 max-lg:pt-[calc(0.5rem+env(safe-area-inset-top))]")}>
          <EchoMindBrand className="text-lg leading-6 lg:hidden" />
          <div className={cn("col-span-2 min-w-0 space-y-1 lg:col-span-1", isPlacesTab && "max-lg:space-y-0")}>
            <p className={cn("text-xs leading-4 font-medium text-muted-foreground", isPlacesTab && "max-lg:hidden")}>Portal do estudante</p>
            <h1 className={cn("text-2xl leading-8 font-semibold tracking-tight [overflow-wrap:anywhere]", isPlacesTab && "max-lg:text-base max-lg:leading-5")}>{companyName}</h1>
          </div>
          <span className="col-start-2 row-start-1 inline-flex items-center gap-2 rounded-full border border-border bg-muted px-3 py-1 text-xs leading-4 font-medium text-success">
            <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-success" />Assistente online
          </span>
        </header>

        <main className={cn("grid min-w-0",
          isPlacesTab ? "min-h-0 lg:grid-rows-[minmax(0,1fr)]" : "gap-6 py-6 pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))] sm:pl-[max(1.5rem,env(safe-area-inset-left))] sm:pr-[max(1.5rem,env(safe-area-inset-right))]",
          activeTab === "chat" && "xl:grid-cols-[minmax(0,1fr)_288px]")}>
          <div className="min-w-0">{children}</div>
          {isPlacesTab && !isDesktop && <div id="portal-campus-directory" ref={placesDirectoryRef} className={styles.mobileDirectory} />}
          {activeTab === "chat" ? <aside data-slot="portal-auxiliary" aria-label="Informações da instituição" className="hidden min-w-0 xl:block">{auxiliary}</aside> : null}
        </main>
        <footer className={cn("px-4 text-sm text-muted-foreground sm:px-6", isPlacesTab ? "py-3" : "pb-6")}><Link href={privacyHref} className="underline underline-offset-4">Privacidade e contato sobre dados pessoais</Link></footer>
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

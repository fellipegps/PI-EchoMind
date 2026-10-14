import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export const mapControlFocus = "scroll-mt-4 scroll-mb-[calc(96px+env(safe-area-inset-bottom))] lg:scroll-mb-4";

export function MapSelect({ className, ...props }: ComponentProps<"select">) {
  return <select {...props} className={cn("h-11 w-full min-w-0 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:opacity-50", mapControlFocus, className)} />;
}

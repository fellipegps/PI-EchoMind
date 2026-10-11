import type { ComponentProps } from "react";
import { Activity, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export function EchoMindBrand({ className, ...props }: ComponentProps<"span">) {
  return (
    <span data-slot="echomind-brand" className={cn("inline-flex items-center gap-3 font-semibold text-foreground", className)} {...props}>
      <span aria-hidden="true" className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Activity className="size-6" />
      </span>
      <span>EchoMind</span>
    </span>
  );
}

export function AssistantAvatar({ className, ...props }: ComponentProps<"span">) {
  return (
    <span data-slot="assistant-avatar" role="img" aria-label="Assistente EchoMind" className={cn("inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-accent text-primary", className)} {...props}>
      <Sparkles aria-hidden="true" className="size-5" />
    </span>
  );
}

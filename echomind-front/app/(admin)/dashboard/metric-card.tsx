import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function MetricCard({ label, value, icon: Icon, tone = "primary" }: {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: "primary" | "success" | "destructive";
}) {
  const tones = {
    primary: "bg-primary/10 text-primary",
    success: "bg-success/10 text-success",
    destructive: "bg-destructive/10 text-destructive",
  };

  return (
    <Card className="min-w-0">
      <CardContent>
        <div className="mb-4 flex items-start justify-between gap-3">
          <p className="min-w-0 text-sm font-medium text-muted-foreground [overflow-wrap:anywhere]">{label}</p>
          <span className={`flex size-10 shrink-0 items-center justify-center rounded-lg ${tones[tone]}`}>
            <Icon aria-hidden="true" className="size-5" />
          </span>
        </div>
        <p className="text-2xl font-bold tracking-tight tabular-nums [overflow-wrap:anywhere]">{value}</p>
      </CardContent>
    </Card>
  );
}

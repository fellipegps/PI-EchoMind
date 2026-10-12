import type { ReactNode } from "react";

export function PageHeader({ title, description, eyebrow, actions }: {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header data-slot="page-header" className="flex min-w-0 flex-col gap-4 [overflow-wrap:anywhere] sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-2">
        {eyebrow && <p className="text-sm leading-5 font-medium text-primary">{eyebrow}</p>}
        <h1 className="text-2xl leading-8 font-semibold tracking-tight">{title}</h1>
        {description && <p className="max-w-3xl text-base leading-6 text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

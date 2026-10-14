import { cn } from "@/lib/utils";

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
  variant?: "standard" | "form" | "wide";
}

const widths = { standard: "max-w-[1200px]", form: "max-w-4xl", wide: "max-w-none" };

export function PageContainer({ children, className, variant = "standard" }: PageContainerProps) {
  return (
    <div data-slot="page-container" data-variant={variant} className={cn(
      "mx-auto w-full min-w-0 flex-1 space-y-6 bg-background p-4 text-foreground md:p-6",
      widths[variant],
      className
    )}>
      {children}
    </div>
  );
}

import { cn } from "@/lib/utils"; // Utilitário padrão do shadcn

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function PageContainer({ children, className }: PageContainerProps) {
  return (
    <div className={cn(
      "p-2 md:p-4 space-y-8 bg-background text-foreground flex-1 overflow-auto",
      className
    )}>
      {children}
    </div>
  );
}
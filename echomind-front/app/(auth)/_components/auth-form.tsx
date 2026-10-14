import type { ComponentProps, ReactNode } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2 } from "lucide-react";
import { EchoMindBrand } from "@/components/echomind-brand";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function AuthPanel({ title, description, children }: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby="auth-title" className="space-y-6">
      <header className="space-y-6 text-center">
        <EchoMindBrand className="text-xl leading-7" />
        <div className="space-y-2">
          <h1 id="auth-title" className="text-2xl leading-8 font-semibold tracking-tight">{title}</h1>
          <p className="text-base leading-6 text-muted-foreground">{description}</p>
        </div>
      </header>
      <Card className="rounded-3xl p-6 sm:p-8">{children}</Card>
    </section>
  );
}

export function AuthForm(props: ComponentProps<"form">) {
  return <form className="space-y-6" {...props} />;
}

export function AuthFields({ children }: { children: ReactNode }) {
  return <div className="space-y-4">{children}</div>;
}

export function AuthField({ id, label, ...props }: ComponentProps<typeof Input> & { id: string; label: string }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} {...props} />
    </div>
  );
}

export function AuthActions({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-3">{children}</div>;
}

export function AuthSubmit({ loading, children }: { loading: boolean; children: ReactNode }) {
  return (
    <Button type="submit" className="w-full" disabled={loading} aria-busy={loading}>
      {loading ? <span aria-hidden="true" className="animate-spin motion-reduce:animate-none"><Loader2 className="size-4" /></span> : null}
      {children}
    </Button>
  );
}

export function AuthLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Button asChild variant="link" className="h-auto min-h-11 w-full whitespace-normal text-center">
      <Link href={href}>{children}</Link>
    </Button>
  );
}

export function AuthSuccess({ children, outline = false }: { children: ReactNode; outline?: boolean }) {
  return (
    <div className="space-y-6 text-center">
      <div role="status" className="space-y-4">
        <CheckCircle2 aria-hidden="true" className="mx-auto size-10 text-success" />
        <p className="text-base leading-6 text-muted-foreground">{children}</p>
      </div>
      <Button asChild variant={outline ? "outline" : "default"} className="w-full">
        <Link href="/login">Voltar para o login</Link>
      </Button>
    </div>
  );
}

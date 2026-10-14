"use client";

import { useState } from "react";
import { AuthActions, AuthField, AuthFields, AuthForm, AuthLink, AuthPanel, AuthSubmit } from "../_components/auth-form";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { authApi } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await authApi.login(email, password);
      await authApi.me();
      toast.success("Login realizado com sucesso!");
      router.push("/dashboard");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Email ou senha incorretos.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthPanel title="Entrar no EchoMind" description="Entre na sua conta para gerenciar seu agente">
      <AuthForm onSubmit={handleLogin}>
        <AuthFields>
          <AuthField id="email" label="Email" type="email" placeholder="admin@echomind.com" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          <AuthField id="password" label="Senha" type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        </AuthFields>
        <AuthActions>
          <AuthSubmit loading={loading}>Entrar</AuthSubmit>
          <Button asChild variant="outline" className="w-full">
            <Link href="/registrar-conta"><UserPlus aria-hidden="true" />Criar conta</Link>
          </Button>
          <AuthLink href="/recuperar-senha">Esqueci minha senha</AuthLink>
        </AuthActions>
      </AuthForm>
    </AuthPanel>
  );
}

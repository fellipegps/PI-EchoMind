"use client";

import { useState } from "react";
import { AuthActions, AuthField, AuthFields, AuthForm, AuthLink, AuthPanel, AuthSubmit } from "../_components/auth-form";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { authApi } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (password.length < 6) {
      toast.error("A senha deve ter pelo menos 6 caracteres");
      return;
    }

    setLoading(true);

    try {
      const result = await authApi.register(email, password, { fullName, companyName });
      toast.success(result.requiresEmailConfirmation
        ? "Cadastro realizado! Verifique seu email para confirmar a conta."
        : "Cadastro realizado! Você já pode entrar na sua conta.");
      router.push("/login");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao criar conta. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthPanel title="Criar Conta" description="Cadastre sua empresa para começar a usar o Agente de IA">
      <AuthForm onSubmit={handleRegister}>
        <AuthFields>
          <AuthField id="company" label="Nome da Empresa" placeholder="Ex: Minha Empresa Tech" value={companyName} onChange={(e) => setCompanyName(e.target.value)} required autoComplete="organization" />
          <AuthField id="name" label="Seu Nome" placeholder="Nome completo" value={fullName} onChange={(e) => setFullName(e.target.value)} required autoComplete="name" />
          <AuthField id="email" label="Email" type="email" placeholder="seu@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          <AuthField id="password" label="Senha" type="password" placeholder="Mínimo 6 caracteres" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
        </AuthFields>
        <AuthActions>
          <AuthSubmit loading={loading}>Criar Conta</AuthSubmit>
          <div className="text-center">
            <p className="text-sm leading-5 text-muted-foreground">Já tem uma conta?</p>
            <AuthLink href="/login">Entrar</AuthLink>
          </div>
        </AuthActions>
      </AuthForm>
    </AuthPanel>
  );
}

"use client";

import { useState } from "react";
import { AuthActions, AuthField, AuthFields, AuthForm, AuthLink, AuthPanel, AuthSubmit, AuthSuccess } from "../_components/auth-form";
import { toast } from "sonner";
import { authApi } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await authApi.resetPassword(email);
      setSent(true);
      toast.success("Email de recuperação enviado!");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Erro ao processar solicitação. Tente novamente."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthPanel title="Recuperar Senha" description="Enviaremos um link para redefinir sua senha">
      {sent ? (
        <AuthSuccess outline>Email enviado com sucesso! Verifique sua caixa de entrada para continuar.</AuthSuccess>
      ) : (
        <AuthForm onSubmit={handleReset}>
          <AuthFields>
            <AuthField id="email" label="Email" type="email" placeholder="seu@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </AuthFields>
          <AuthActions>
            <AuthSubmit loading={loading}>Enviar Link</AuthSubmit>
            <AuthLink href="/login">Voltar para o login</AuthLink>
          </AuthActions>
        </AuthForm>
      )}
    </AuthPanel>
  );
}

"use client";

import { useState } from "react";
import { AuthActions, AuthField, AuthFields, AuthForm, AuthLink, AuthPanel, AuthSubmit, AuthSuccess } from "../_components/auth-form";
import { toast } from "sonner";
import { supabase } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [updated, setUpdated] = useState(false);

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password.length < 6) {
      toast.error("A senha deve ter pelo menos 6 caracteres");
      return;
    }

    if (password !== confirmPassword) {
      toast.error("As senhas nao conferem");
      return;
    }

    setLoading(true);

    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) {
        throw new Error(error.message);
      }

      setUpdated(true);
      toast.success("Senha atualizada com sucesso!");
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Nao foi possivel atualizar a senha. Solicite um novo link."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthPanel title="Redefinir senha" description="Escolha uma nova senha para sua conta">
      {updated ? (
        <AuthSuccess>Sua senha foi atualizada. Voce ja pode acessar sua conta.</AuthSuccess>
      ) : (
        <AuthForm onSubmit={handleUpdatePassword}>
          <AuthFields>
            <AuthField id="password" label="Nova senha" type="password" placeholder="Minimo 6 caracteres" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
            <AuthField id="confirm-password" label="Confirmar senha" type="password" placeholder="Digite novamente" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required autoComplete="new-password" />
          </AuthFields>
          <AuthActions>
            <AuthSubmit loading={loading}>Atualizar senha</AuthSubmit>
            <AuthLink href="/login">Voltar para o login</AuthLink>
          </AuthActions>
        </AuthForm>
      )}
    </AuthPanel>
  );
}

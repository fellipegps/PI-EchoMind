"use client";

import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PrivacySettings } from "@/lib/api";

export function PrivacySettingsCard({ value, onChange, onSave, saving }: {
  value: PrivacySettings;
  onChange: (update: PrivacySettings) => void;
  onSave: () => void;
  saving: boolean;
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); onSave(); };
  return (
    <form onSubmit={submit} aria-label="Configurações de privacidade" aria-busy={saving}>
      <Card>
        <CardHeader>
          <CardTitle><h2 className="text-lg">Privacidade e retenção</h2></CardTitle>
          <CardDescription>Estas informações serão publicadas no aviso da instituição. Preencha os dados aprovados pelo responsável por privacidade.</CardDescription>
          <p className="text-sm text-muted-foreground">Você pode salvar as informações do aviso enquanto o cadastro estiver em revisão.</p>
          <p role="status" className="text-sm text-muted-foreground">{value.privacy_ready ? "Informações de privacidade cadastradas." : "Informações de privacidade incompletas. Você pode continuar testando o chat."}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2"><Label htmlFor="privacy-controller">Instituição responsável pelos dados</Label>
            <Input id="privacy-controller" minLength={2} maxLength={200} value={value.privacy_controller ?? ""} onChange={e => onChange({ privacy_controller: e.target.value })} />
            <p className="text-sm text-muted-foreground">Informe quem decide para que e como os dados deste atendimento serão usados.</p>
          </div>
          <div className="space-y-2"><Label htmlFor="privacy-email">E-mail para pedidos de privacidade</Label>
            <Input id="privacy-email" type="email" maxLength={320} value={value.privacy_email ?? ""} onChange={e => onChange({ privacy_email: e.target.value })} aria-describedby="privacy-email-help" />
            <p id="privacy-email-help" className="text-sm text-muted-foreground">Use um endereço monitorado pela equipe para receber pedidos de acesso, correção e eliminação de dados.</p>
          </div>
          <div className="space-y-2"><Label htmlFor="privacy-purpose">Finalidade do uso dos dados no chat</Label>
            <Textarea id="privacy-purpose" minLength={10} maxLength={1000} value={value.privacy_purpose ?? ""} onChange={e => onChange({ privacy_purpose: e.target.value })} />
          </div>
          <div className="space-y-2"><Label htmlFor="privacy-legal-basis">Base legal definida pela instituição</Label>
            <Textarea id="privacy-legal-basis" minLength={5} maxLength={1000} value={value.privacy_legal_basis ?? ""} onChange={e => onChange({ privacy_legal_basis: e.target.value })} aria-describedby="privacy-basis-help" />
            <p id="privacy-basis-help" className="text-sm text-muted-foreground">Confirme a justificativa com o responsável. O preenchimento não substitui a avaliação da base legal; consentimento, quando necessário, exige coleta específica.</p>
          </div>
          <section className="space-y-2 border-t pt-4" aria-labelledby="privacy-retention">
            <h3 id="privacy-retention" className="text-sm font-medium">Prazo de retenção do histórico</h3>
            <p>{value.chat_retention_days ? `${value.chat_retention_days} dias` : "Prazo indisponível."}</p>
            <p className="text-sm text-muted-foreground">
              A operação do EchoMind define este prazo.
              {value.chat_retention_enabled === true && " A limpeza automática remove interações e itens da triagem que ultrapassam o prazo."}
              {value.chat_retention_enabled === false && " A limpeza automática está desativada no servidor."}
            </p>
          </section>
        </CardContent>
        <CardFooter><Button type="submit" disabled={saving}>{saving ? "Salvando privacidade…" : "Salvar privacidade"}</Button></CardFooter>
      </Card>
    </form>
  );
}

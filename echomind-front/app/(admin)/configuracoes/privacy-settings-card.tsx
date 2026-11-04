"use client";

import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
          <p className="text-sm text-muted-foreground">Com a limpeza desativada, você pode salvar um cadastro incompleto. O chat público só é liberado após concluir as informações e ativar a limpeza.</p>
          <p role="status" className="text-sm text-muted-foreground">{value.privacy_ready ? "Informações de privacidade cadastradas. Atendimento público liberado." : "Conclua os campos e ative a limpeza para liberar o chat público. Eventos e mapas continuam disponíveis."}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2"><Label htmlFor="privacy-controller">Instituição responsável pelos dados</Label>
            <Input id="privacy-controller" required={value.chat_retention_enabled === true} minLength={2} maxLength={200} value={value.privacy_controller ?? ""} onChange={e => onChange({ privacy_controller: e.target.value })} />
            <p className="text-sm text-muted-foreground">Informe quem decide para que e como os dados deste atendimento serão usados.</p>
          </div>
          <div className="space-y-2"><Label htmlFor="privacy-email">E-mail para pedidos de privacidade</Label>
            <Input id="privacy-email" type="email" required={value.chat_retention_enabled === true} maxLength={320} value={value.privacy_email ?? ""} onChange={e => onChange({ privacy_email: e.target.value })} aria-describedby="privacy-email-help" />
            <p id="privacy-email-help" className="text-sm text-muted-foreground">Use um endereço monitorado pela equipe para receber pedidos de acesso, correção e eliminação de dados.</p>
          </div>
          <div className="space-y-2"><Label htmlFor="privacy-purpose">Finalidade do uso dos dados no chat</Label>
            <Textarea id="privacy-purpose" required={value.chat_retention_enabled === true} minLength={10} maxLength={1000} value={value.privacy_purpose ?? ""} onChange={e => onChange({ privacy_purpose: e.target.value })} />
          </div>
          <div className="space-y-2"><Label htmlFor="privacy-legal-basis">Base legal definida pela instituição</Label>
            <Textarea id="privacy-legal-basis" required={value.chat_retention_enabled === true} minLength={5} maxLength={1000} value={value.privacy_legal_basis ?? ""} onChange={e => onChange({ privacy_legal_basis: e.target.value })} aria-describedby="privacy-basis-help" />
            <p id="privacy-basis-help" className="text-sm text-muted-foreground">Confirme a justificativa com o responsável. O preenchimento não substitui a avaliação da base legal; consentimento, quando necessário, exige coleta específica.</p>
          </div>
          <div className="space-y-2"><Label htmlFor="privacy-retention">Prazo do histórico de chat, em dias</Label>
            <Input id="privacy-retention" type="number" required={value.chat_retention_enabled === true} min={1} max={3650} step={1} value={value.chat_retention_days ?? ""} onChange={e => onChange({ chat_retention_days: e.target.value ? Number(e.target.value) : null })} />
            <p className="text-sm text-muted-foreground">Não existe um prazo único obrigatório. Escolha o período aprovado para a finalidade informada.</p>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-4"><Label htmlFor="privacy-cleanup">Ativar limpeza automática do histórico</Label>
              <Switch id="privacy-cleanup" checked={value.chat_retention_enabled ?? false} onCheckedChange={checked => onChange({ chat_retention_enabled: checked })} aria-describedby="privacy-cleanup-help" />
            </div>
            <p id="privacy-cleanup-help" className="text-sm text-muted-foreground">Ao salvar com esta opção ativa, conversas e perguntas não respondidas anteriores ao prazo serão excluídas na próxima execução, em até uma hora enquanto a API estiver ativa. A exclusão é definitiva. Documentos, FAQs publicadas, contas, backups e dados dos fornecedores precisam de tratamento separado.</p>
          </div>
        </CardContent>
        <CardFooter><Button type="submit" disabled={saving}>{saving ? "Salvando privacidade…" : "Salvar privacidade"}</Button></CardFooter>
      </Card>
    </form>
  );
}

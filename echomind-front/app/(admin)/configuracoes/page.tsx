"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { PageContainer } from "@/components/page-container";
import { configApi } from "@/lib/api";
import type { Config } from "@/lib/api";
import { PublicPortalCard } from "./public-portal-card";

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState<Partial<Config>>({
    company_name: "",
    description: "",
    tone_of_voice: "profissional e cordial",
    chat_voice_gender: "feminina",
    website: "",
    phone: "",
    address: "",
    business_hours: "",
  });

  // ─── Carrega configuração do backend ──────────────────────────────────────
  useEffect(() => {
    configApi
      .get()
      .then((cfg) => setForm(cfg))
      .catch(() => {
        // Sem config ainda — usa defaults (backend vai criar no PUT)
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await configApi.save(form);
      setForm(updated);
      toast.success("Configurações atualizadas com sucesso!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <PageContainer variant="form">
        <PageHeader title="Configurações do Sistema" description="Gerencie a identidade institucional e o comportamento do EchoMind" />
        <div role="status" aria-label="Carregando configurações" className="space-y-6">
          <p className="text-sm text-muted-foreground">Carregando configurações…</p>
          <Skeleton aria-hidden="true" className="h-96 w-full motion-reduce:animate-none" />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer variant="form">
      <PageHeader title="Configurações do Sistema" description="Gerencie a identidade institucional e o comportamento do EchoMind" />

      <div className="grid gap-6">
        <Card className="gap-5 overflow-hidden pb-0">
          <CardHeader className="px-4 md:px-6">
            <CardTitle><h2 className="text-lg">Dados da Instituição</h2></CardTitle>
            <CardDescription>
              Informações essenciais para a calibração das respostas da IA.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 px-4 md:px-6">
            <fieldset className="min-w-0 space-y-4">
              <legend className="mb-4 text-sm font-semibold">Identidade institucional</legend>
            <div className="space-y-2">
              <Label htmlFor="settings-company_name">Nome da Instituição</Label>
              <Input
                id="settings-company_name"
                value={form.company_name ?? ""}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                placeholder="Ex: UniEVANGÉLICA"
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="settings-description">Descrição Base (Contexto)</Label>
              <Textarea
                id="settings-description"
                value={form.description ?? ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Descreva o que sua instituição faz, seus diferenciais e público-alvo..."
                rows={4}
                className="min-h-32 max-h-64 resize-none overflow-y-auto bg-background [field-sizing:fixed]"
              />
            </div>

            </fieldset>
            <fieldset className="min-w-0 space-y-4 border-t pt-6">
              <legend className="mb-4 text-sm font-semibold">Comportamento do agente</legend>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="settings-tone_of_voice">Personalidade da IA</Label>
                <Select
                  value={form.tone_of_voice ?? "profissional e cordial"}
                  onValueChange={(v) => setForm({ ...form, tone_of_voice: v })}
                >
                  <SelectTrigger id="settings-tone_of_voice" className="bg-background"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="profissional e cordial">Profissional e cordial</SelectItem>
                    <SelectItem value="descontraído e jovem">Descontraído e jovem</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="settings-chat_voice_gender">Voz do Chatbot</Label>
                <Select
                  value={form.chat_voice_gender ?? "feminina"}
                  onValueChange={(v) => setForm({ ...form, chat_voice_gender: v })}
                >
                  <SelectTrigger id="settings-chat_voice_gender" className="bg-background"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="feminina">Feminina (pt-BR)</SelectItem>
                    <SelectItem value="masculina">Masculino (pt-BR)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            </fieldset>
            <fieldset className="min-w-0 space-y-4 border-t pt-6">
              <legend className="mb-4 text-sm font-semibold">Contato e atendimento</legend>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="settings-website">Website Oficial</Label>
                <Input
                id="settings-website"
                  value={form.website ?? ""}
                  onChange={(e) => setForm({ ...form, website: e.target.value })}
                  className="bg-background"
                  placeholder="https://www.exemplo.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="settings-phone">Telefone de Contato</Label>
                <Input
                id="settings-phone"
                  value={form.phone ?? ""}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="bg-background"
                  placeholder="(11) 99999-9999"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="settings-address">Endereço</Label>
              <Input
                id="settings-address"
                value={form.address ?? ""}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                className="bg-background"
                placeholder="Rua, número, bairro, cidade - UF"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="settings-business_hours">Horário de Funcionamento</Label>
              <Input
                id="settings-business_hours"
                value={form.business_hours ?? ""}
                onChange={(e) => setForm({ ...form, business_hours: e.target.value })}
                className="bg-background"
                placeholder="Ex: Seg-Sex 9h-18h, Sáb 9h-13h"
              />
            </div>
            </fieldset>
          </CardContent>
          <CardFooter className="border-t bg-muted/20 px-4 py-4 [.border-t]:pt-4 md:px-6">
            <Button onClick={handleSave} disabled={saving} aria-busy={saving} className="w-full sm:w-auto sm:min-w-40">
              {saving && <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin motion-reduce:animate-none" />}
              {saving ? "Salvando…" : "Salvar Alterações"}
            </Button>
          </CardFooter>
        </Card>

        <PublicPortalCard publicSlug={form.public_slug ?? ""} />
      </div>
    </PageContainer>
  );
}

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
import { Loader2, Copy, LinkIcon } from "lucide-react";
import { PageContainer } from "@/components/page-container";
import { configApi } from "@/lib/api";
import type { Config } from "@/lib/api";

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState<Partial<Config>>({
    company_name: "",
    description: "",
    tone_of_voice: "profissional e cordial",
    totem_voice_gender: "feminina",
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
    } catch (err: any) {
      toast.error(err.message ?? "Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  };

  const chatbotUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/agente-publico`
      : "";

  const copyUrl = () => {
    navigator.clipboard.writeText(chatbotUrl);
    toast.success("URL copiada!");
  };

  if (loading) {
    return (
      <PageContainer className="space-y-8 max-w-4xl">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 w-full" />
      </PageContainer>
    );
  }

  return (
    <PageContainer className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Configurações do Sistema</h1>
        <p className="text-muted-foreground mt-1">
          Gerencie a identidade institucional e o comportamento do EchoMind
        </p>
      </div>

      <div className="grid gap-6">
        <Card className="border-border bg-card pb-0 pt-4">
          <CardHeader className="pb-4">
            <CardTitle className="text-2xl">Dados da Instituição</CardTitle>
            <CardDescription>
              Informações essenciais para a calibração das respostas da IA.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label>Nome da Instituição</Label>
              <Input
                value={form.company_name ?? ""}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                placeholder="Ex: UniEVANGÉLICA"
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label>Descrição Base (Contexto)</Label>
              <Textarea
                value={form.description ?? ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Descreva o que sua instituição faz, seus diferenciais e público-alvo..."
                rows={4}
                className="bg-background resize-none"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label>Personalidade da IA</Label>
                <Select
                  value={form.tone_of_voice ?? "profissional e cordial"}
                  onValueChange={(v) => setForm({ ...form, tone_of_voice: v })}
                >
                  <SelectTrigger className="bg-background"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="profissional e cordial">Profissional e cordial</SelectItem>
                    <SelectItem value="descontraído e jovem">Descontraído e jovem</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Voz do Totem</Label>
                <Select
                  value={form.totem_voice_gender ?? "feminina"}
                  onValueChange={(v) => setForm({ ...form, totem_voice_gender: v })}
                >
                  <SelectTrigger className="bg-background"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="feminina">Feminina</SelectItem>
                    <SelectItem value="masculina">Masculina</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label>Website Oficial</Label>
                <Input
                  value={form.website ?? ""}
                  onChange={(e) => setForm({ ...form, website: e.target.value })}
                  className="bg-background"
                  placeholder="https://www.exemplo.com"
                />
              </div>
              <div className="space-y-2">
                <Label>Telefone de Contato</Label>
                <Input
                  value={form.phone ?? ""}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="bg-background"
                  placeholder="(11) 99999-9999"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Endereço</Label>
              <Input
                value={form.address ?? ""}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                className="bg-background"
                placeholder="Rua, número, bairro, cidade - UF"
              />
            </div>

            <div className="space-y-2">
              <Label>Horário de Funcionamento</Label>
              <Input
                value={form.business_hours ?? ""}
                onChange={(e) => setForm({ ...form, business_hours: e.target.value })}
                className="bg-background"
                placeholder="Ex: Seg-Sex 9h-18h, Sáb 9h-13h"
              />
            </div>
          </CardContent>
          <CardFooter className="px-6 py-4">
            <Button onClick={handleSave} disabled={saving} className="min-w-35">
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Salvar Alterações"}
            </Button>
          </CardFooter>
        </Card>

        <Card className="bg-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2 text-primary">
              <LinkIcon className="h-5 w-5" />
              <CardTitle className="text-lg">Link do Totem</CardTitle>
            </div>
            <CardDescription>URL pública para acesso à interface do assistente.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input
                value={chatbotUrl}
                readOnly
                className="font-mono text-sm bg-background border-primary/20"
              />
              <Button variant="outline" size="icon" onClick={copyUrl} className="shrink-0">
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}

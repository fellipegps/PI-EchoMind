"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Copy, LinkIcon } from "lucide-react";
import { PageContainer } from "@/components/page-container";

export default function SettingsPage() {
  const [saving, setSaving] = useState(false);
  const [companyId] = useState("12345");
  const [companyName, setCompanyName] = useState("UniEVANGÉLICA");
  const [description, setDescription] = useState("");
  const [toneOfVoice, setToneOfVoice] = useState("profissional e cordial");
  const [totemVoiceGender, setTotemVoiceGender] = useState("feminina");
  const [website, setWebsite] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [businessHours, setBusinessHours] = useState("");

  const handleSave = () => {
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      toast.success("Configurações atualizadas com sucesso!");
    }, 1000);
  };

  const chatbotUrl = typeof window !== "undefined" 
    ? `${window.location.origin}/chat/${companyId}` 
    : "";

  const copyUrl = () => {
    navigator.clipboard.writeText(chatbotUrl);
    toast.success("URL copiada!");
  };

  return (
    <PageContainer className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Configurações do Sistema</h1>
        <p className="text-muted-foreground mt-1">Gerencie a identidade institucional e o comportamento do EchoMind</p>
      </div>

      <div className="grid gap-6">
        {/* Card Principal de Dados */}
        <Card className="border-border bg-card pb-0 pt-4">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2">
              <CardTitle className="text-2xl">Dados da Instituição</CardTitle>
            </div>
            <CardDescription>
              Informações essenciais para a calibração das respostas da IA.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Nome da Instituição</Label>
              <Input 
                value={companyName} 
                onChange={(e) => setCompanyName(e.target.value)} 
                placeholder="Ex: UniEVANGÉLICA"
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Descrição Base (Contexto)</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Descreva o que sua empresa faz, seus diferenciais e público-alvo..."
                rows={4}
                className="bg-background resize-none"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label className="text-sm font-medium">Personalidade da IA</Label>
                <Select value={toneOfVoice} onValueChange={setToneOfVoice}>
                  <SelectTrigger className="bg-background">
                    <SelectValue placeholder="Selecione o tom" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="profissional e cordial">Profissional e cordial</SelectItem>
                    <SelectItem value="descontraído e jovem">Descontraído e jovem</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-sm font-medium">Voz do Totem</Label>
                <Select value={totemVoiceGender} onValueChange={setTotemVoiceGender}>
                  <SelectTrigger className="bg-background">
                    <SelectValue placeholder="Selecione o gênero" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="feminina">Feminina</SelectItem>
                    <SelectItem value="masculina">Masculina</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label className="text-sm font-medium">Website Oficial</Label>
                <Input value={website} onChange={(e) => setWebsite(e.target.value)} className="bg-background" placeholder="https://www.exemplo.com" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm font-medium">Telefone de Contato</Label>
                <Input value={phone} onChange={(e) => setPhone(e.target.value)} className="bg-background" placeholder="(11) 99999-9999" />
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Endereço</Label>
              <Input value={address} onChange={(e) => setAddress(e.target.value)} className="bg-background" placeholder="Rua, número, bairro, cidade - UF" />
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Horário de Funcionamento</Label>
              <Input value={businessHours} onChange={(e) => setBusinessHours(e.target.value)} className="bg-background" placeholder="Ex: Seg-Sex 9h-18h, Sáb 9h-13h" />
            </div>
          </CardContent>
          <CardFooter className="px-6 py-4 flex justify-start">
            <Button onClick={handleSave} disabled={saving} className="min-w-35">
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Salvar Alterações"}
            </Button>
          </CardFooter>
        </Card>

        {/* Card de URL - Estilo Link de Integração */}
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
              <Input value={chatbotUrl} readOnly className="font-mono text-sm bg-background border-primary/20" />
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
"use client";

import { useState } from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { Check, Inbox, Loader2, Plus, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { EchoMindBrand, AssistantAvatar } from "@/components/echomind-brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

const swatches = ["primary", "background", "card", "muted", "foreground", "success", "warning", "destructive", "ring"];

export function DesignSystemSample() {
  const { setTheme } = useTheme();
  const [count, setCount] = useState(0);
  const [selected, setSelected] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [saved, setSaved] = useState(false);

  return (
    <main className="mx-auto max-w-[1200px] space-y-8 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <EchoMindBrand />
        <div className="flex flex-wrap gap-2" aria-label="Tema da amostra">
          <Button variant="outline" size="sm" onClick={() => setTheme("light")}>Claro</Button>
          <Button variant="outline" size="sm" onClick={() => setTheme("dark")}>Escuro</Button>
          <Button variant="outline" size="sm" onClick={() => setTheme("system")}>Sistema</Button>
        </div>
      </header>
      <section className="space-y-2">
        <Badge variant="secondary">DS-01 · somente desenvolvimento</Badge>
        <h1 className="text-[28px] leading-9 font-semibold md:text-4xl md:leading-10">A inteligência que acolhe e orienta.</h1>
        <p className="text-muted-foreground">Fundamentos, componentes e estados para revisão. Nenhum dado é enviado por esta amostra.</p>
      </section>
      <section aria-label="Paleta semântica" className="grid grid-cols-3 gap-3 md:grid-cols-9">
        {swatches.map(token => <div key={token} className="space-y-2"><div className="h-12 rounded-sm border" style={{ backgroundColor: `var(--${token})` }} /><p className="text-xs leading-4 text-muted-foreground">{token}</p></div>)}
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Botões e interação</CardTitle><CardDescription>Normal, hover, foco, pressionado e desabilitado.</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => setCount(c => c + 1)}>Ação principal</Button>
              <Button variant="secondary" onClick={() => setCount(c => c + 1)}>Secundário</Button>
              <Button variant="outline" onClick={() => setCount(c => c + 1)}>Contornado</Button>
              <Button variant="ghost" onClick={() => setCount(c => c + 1)}>Discreto</Button>
              <Button variant="destructive" onClick={() => setCount(c => c + 1)}>Destrutivo</Button>
              <Button size="icon" aria-label="Adicionar item de teste" onClick={() => setCount(c => c + 1)}><Plus /></Button>
              <Button asChild variant="link"><Link href="#formulario">Ir ao formulário</Link></Button>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button disabled>Indisponível</Button>
              <Button disabled aria-busy="true"><Loader2 className="animate-spin motion-reduce:animate-none" />Carregando…</Button>
              <Button variant="outline" aria-pressed={selected} onClick={() => setSelected(v => !v)} className={selected ? "bg-accent text-accent-foreground shadow-inner" : undefined}>Alternável {selected ? "ativo" : "inativo"}</Button>
            </div>
            <p role="status" className="text-sm text-muted-foreground">Ações executadas: {count}</p>
            <div className="flex flex-wrap gap-2"><Badge>Primário</Badge><Badge variant="secondary">Secundário</Badge><Badge variant="outline">Contorno</Badge><Badge variant="success"><Check />Sucesso</Badge><Badge variant="warning">Aviso</Badge><Badge variant="destructive">Erro</Badge></div>
            <div className="flex items-center gap-3"><AssistantAvatar /><p className="text-sm">Avatar do assistente, distinto da marca.</p></div>
          </CardContent>
        </Card>
        <Card id="formulario">
          <CardHeader><CardTitle>Campos e validação</CardTitle><CardDescription>Rótulos associados, texto longo e mensagens legíveis.</CardDescription></CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={e => { e.preventDefault(); setSaved(true); }}>
              <div className="space-y-2"><Label htmlFor="sample-email">E-mail de teste</Label><Input id="sample-email" type="email" required placeholder="pessoa@example.test" aria-invalid={invalid} aria-describedby={invalid ? "sample-error" : undefined} />{invalid && <p id="sample-error" role="alert" className="text-sm text-destructive">Confira o endereço de e-mail antes de continuar.</p>}</div>
              <div className="space-y-2"><Label htmlFor="sample-description">Descrição</Label><Textarea id="sample-description" placeholder="Uma descrição que pode ocupar mais de uma linha." /></div>
              <div className="space-y-2"><Label htmlFor="sample-select">Opção de teste</Label><Select defaultValue="first"><SelectTrigger id="sample-select" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="first">Primeira opção</SelectItem><SelectItem value="second">Segunda opção</SelectItem><SelectItem value="disabled" disabled>Opção indisponível</SelectItem></SelectContent></Select></div>
              <div className="space-y-2"><Label htmlFor="sample-disabled">Campo indisponível</Label><Input id="sample-disabled" disabled value="Texto preservado e legível" /></div>
              <div className="flex flex-wrap gap-3"><Button type="submit">Validar amostra</Button><Button type="button" variant="outline" onClick={() => setInvalid(v => !v)}>Alternar erro de campo</Button></div>
              {saved && <p role="status" className="text-sm text-success">Amostra validada localmente.</p>}
            </form>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Estados e notificações</CardTitle><CardDescription>Sem dados ilustrativos na navegação do produto.</CardDescription></CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border p-4"><Inbox aria-hidden="true" className="mb-2 size-5 text-muted-foreground" /><p className="font-medium">Nenhum item de teste</p><p className="text-sm text-muted-foreground">Estado vazio sem ação inventada.</p></div>
            <div className="rounded-xl border p-4"><TriangleAlert aria-hidden="true" className="mb-2 size-5 text-destructive" /><p className="text-sm text-destructive">Não foi possível concluir a operação de teste.</p></div>
            <div className="rounded-xl border p-4"><Check aria-hidden="true" className="mb-2 size-5 text-success" /><p className="text-sm text-success">Operação de teste concluída.</p></div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => toast.success("Notificação de teste concluída.", {description:"Mensagem e ícone preservados no tema atual."})}>Notificação de sucesso</Button>
            <Button variant="outline" onClick={() => toast.error("Falha de teste.")}>Notificação de erro</Button>
            <Dialog><DialogTrigger asChild><Button variant="outline">Abrir diálogo</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Diálogo de revisão</DialogTitle><DialogDescription>Teste o foco, Escape e retorno ao botão de abertura.</DialogDescription></DialogHeader><Input aria-label="Campo do diálogo" placeholder="Campo com foco inicial" /></DialogContent></Dialog>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}

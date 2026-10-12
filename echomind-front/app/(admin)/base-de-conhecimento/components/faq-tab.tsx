"use client";

import { useRef, useState } from "react";
import { BookOpen, Loader2, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useFaqs } from "../hooks/use-faqs";
import type { Faq } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function FaqTab() {
  const { faqs, loading, saveFaq, deleteFaq, toggleChatbotStatus } = useFaqs();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<Faq | null>(null);
  const [form, setForm] = useState({ question: "", answer: "" });
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const dialogOrigin = useRef<HTMLButtonElement | null>(null);

  const filteredFaqs = faqs.filter(f =>
    f.question.toLowerCase().includes(search.toLowerCase())
  );

  const openDialog = (origin: HTMLButtonElement, faq?: Faq) => {
    dialogOrigin.current = origin;
    setEditingFaq(faq || null);
    setForm(faq ? { question: faq.question, answer: faq.answer } : { question: "", answer: "" });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (savingRef.current) return;
    if (!form.question.trim() || !form.answer.trim()) {
      toast.error("Preencha todos os campos");
      return;
    }
    savingRef.current = true;
    setSaving(true);
    try {
      await saveFaq(form, editingFaq?.id || null);
      setDialogOpen(false);
    } catch {
      // O hook comunica o erro; conservar diálogo e conteúdo para correção.
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!savingRef.current) setDialogOpen(open);
  };

  return (
    <section className="min-w-0 space-y-6" aria-labelledby="faq-heading">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h2 id="faq-heading" className="text-lg font-semibold">Perguntas frequentes</h2>
          <p className="text-sm text-muted-foreground">Organize as respostas e escolha quais FAQs exibir no chatbot.</p>
        </div>
        <Button onClick={(event) => openDialog(event.currentTarget)} className="shrink-0">
          <Plus aria-hidden="true" />Nova FAQ
        </Button>
      </div>

      <div className="max-w-xl space-y-2">
        <Label htmlFor="faq-search">Buscar por pergunta</Label>
        <div className="relative">
          <Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input id="faq-search" placeholder="Digite parte da pergunta" value={search}
            onChange={(event) => setSearch(event.target.value)} className="pl-10" />
        </div>
      </div>

      <Card className="min-w-0 py-0">
        <CardContent className="min-w-0 p-0">
          {loading ? (
            <div role="status" className="flex min-h-48 items-center justify-center gap-3 p-6 text-sm text-muted-foreground">
              <Loader2 aria-hidden="true" className="size-5 animate-spin motion-reduce:animate-none" />Carregando FAQs...
            </div>
          ) : filteredFaqs.length === 0 ? (
            <div role="status" className="flex min-h-48 flex-col items-center justify-center gap-3 p-6 text-center">
              <BookOpen aria-hidden="true" className="size-6 text-muted-foreground" />
              <p className="font-medium">{search ? "Nenhuma pergunta encontrada" : "Nenhuma FAQ disponível nesta lista"}</p>
              <p className="max-w-md text-sm text-muted-foreground">
                {search ? "Tente outro termo na busca por pergunta." : "Quando FAQs forem carregadas, elas aparecerão aqui."}
              </p>
            </div>
          ) : (
            <ul aria-label="Perguntas frequentes" className="divide-y divide-border">
              {filteredFaqs.map((faq) => (
                <li key={faq.id} className="grid min-w-0 gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:gap-6 md:p-6">
                  <div className="min-w-0 space-y-3">
                    <h3 className="text-base font-semibold whitespace-pre-wrap [overflow-wrap:anywhere]">{faq.question}</h3>
                    <p className="text-sm leading-6 whitespace-pre-wrap text-muted-foreground [overflow-wrap:anywhere]">{faq.answer}</p>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 xl:flex-col xl:items-end xl:justify-start">
                    <Badge variant={faq.show_in_chatbot ? "default" : "secondary"}>
                      {faq.show_in_chatbot ? "No Chatbot" : "Oculta"}
                    </Badge>
                    <Label htmlFor={`faq-chatbot-${faq.id}`} className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
                      Exibir no chatbot
                      <Switch id={`faq-chatbot-${faq.id}`} checked={faq.show_in_chatbot}
                        aria-label={`Exibir no chatbot: ${faq.question}`}
                        onCheckedChange={() => toggleChatbotStatus(faq.id)} />
                    </Label>
                    <div className="flex gap-2">
                      <Button variant="outline" size="icon" aria-label={`Editar FAQ: ${faq.question}`}
                        onClick={(event) => openDialog(event.currentTarget, faq)}>
                        <Pencil aria-hidden="true" />
                      </Button>
                      <Button variant="outline" size="icon" aria-label={`Excluir FAQ: ${faq.question}`}
                        onClick={() => deleteFaq(faq.id)} className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                        <Trash2 aria-hidden="true" />
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={handleOpenChange}>
        <DialogContent showCloseButton={false} className="max-h-[calc(100dvh-2rem)] overflow-y-auto"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            dialogOrigin.current?.focus();
          }}>
          <DialogHeader className="pr-8 text-left">
            <DialogTitle>{editingFaq ? "Editar FAQ" : "Nova FAQ"}</DialogTitle>
            <DialogDescription>Preencha a pergunta e a resposta. Ambos os campos são obrigatórios.</DialogDescription>
          </DialogHeader>
          <DialogClose asChild>
            <Button variant="ghost" size="icon" aria-label="Fechar formulário de FAQ" disabled={saving} className="absolute right-2 top-2">
              <X aria-hidden="true" />
            </Button>
          </DialogClose>
          <form className="min-w-0 space-y-6" aria-label="Formulário de FAQ" aria-busy={saving}
            onSubmit={(event) => { event.preventDefault(); void handleSave(); }}>
            <div className="space-y-2">
              <Label htmlFor="faq-question">Pergunta</Label>
              <Textarea id="faq-question" value={form.question} rows={3} aria-required="true"
                onChange={(event) => setForm({ ...form, question: event.target.value })} disabled={saving}
                className="min-h-24 max-h-[25dvh] [overflow-wrap:anywhere]" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="faq-answer">Resposta</Label>
              <Textarea id="faq-answer" value={form.answer} rows={5} aria-required="true"
                onChange={(event) => setForm({ ...form, answer: event.target.value })} disabled={saving}
                className="min-h-32 max-h-[25dvh] [overflow-wrap:anywhere]" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={saving}>Cancelar</Button>
              <Button type="submit" disabled={saving}>
                {saving ? <><Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" />Salvando...</> : "Salvar"}
              </Button>
            </DialogFooter>
            {saving && <p role="status" className="sr-only">Salvando FAQ. Aguarde a conclusão.</p>}
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}

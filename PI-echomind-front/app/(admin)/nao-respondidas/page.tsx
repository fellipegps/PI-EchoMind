"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Search, MessageSquarePlus, ChevronDown, ChevronUp, HelpCircle } from "lucide-react";
import { toast } from "sonner";
import { PageContainer } from "@/components/page-container";
import { Label } from "@/components/ui/label";
import { unansweredApi } from "@/lib/api";
import type { UnansweredQuestion } from "@/lib/api";

export default function UnansweredQuestions() {
  const [questions, setQuestions] = useState<UnansweredQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [converting, setConverting] = useState<string | null>(null);

  // ─── Carrega perguntas não respondidas do backend ─────────────────────────
  useEffect(() => {
    unansweredApi
      .list()
      .then(setQuestions)
      .catch(() => toast.error("Erro ao carregar perguntas."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = questions.filter((q) =>
    q.canonical_question.toLowerCase().includes(search.toLowerCase())
  );

  const convertToFaq = async (id: string) => {
    if (!answer.trim()) {
      toast.error("Por favor, escreva uma resposta.");
      return;
    }
    setConverting(id);
    try {
      await unansweredApi.convert(id, answer);
      setQuestions((prev) => prev.filter((q) => q.id !== id));
      setAnswer("");
      toast.success("Resposta convertida em FAQ oficial com sucesso!");
    } catch (err: any) {
      toast.error(err.message ?? "Erro ao converter.");
    } finally {
      setConverting(null);
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });

  if (loading) {
    return (
      <PageContainer className="space-y-6">
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </PageContainer>
    );
  }

  return (
    <PageContainer className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Perguntas Não Respondidas</h1>
        <p className="text-muted-foreground mt-1 text-base">
          Analise o que o EchoMind ainda não sabe e transforme em conhecimento oficial.
        </p>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Pesquisar perguntas..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-card border-border"
        />
      </div>

      <div className="grid gap-4">
        {filtered.map((q) => (
          <Card key={q.id} className="border-border bg-card hover:shadow-sm transition-shadow">
            <CardContent className="px-4 py-3">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <p className="text-lg font-semibold text-foreground">{q.canonical_question}</p>
                    <Badge variant="secondary" className="bg-primary/10 text-primary border-none">
                      {q.count} {q.count === 1 ? "ocorrência" : "ocorrências"}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-2 text-sm text-muted-foreground mt-2">
                    <span>Primeira vez: {formatDate(q.first_asked)}</span>
                    <span>•</span>
                    <span>Última vez: {formatDate(q.last_asked)}</span>
                  </div>

                  {q.similar_questions.length > 0 && (
                    <div className="mt-4">
                      <button
                        onClick={() => setExpanded(expanded === q.id ? null : q.id)}
                        className="text-sm text-primary flex items-center gap-1 font-medium hover:opacity-80"
                      >
                        {expanded === q.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        Ver {q.similar_questions.length} variações detectadas
                      </button>

                      {expanded === q.id && (
                        <div className="mt-3 space-y-2 pl-4 border-l-2 border-primary/20 bg-muted/30 p-3 rounded-r-lg">
                          {q.similar_questions.map((sq, i) => (
                            <p key={i} className="text-sm text-muted-foreground italic">"{sq}"</p>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <Dialog onOpenChange={(open) => { if (!open) setAnswer(""); }}>
                  <DialogTrigger asChild>
                    <Button className="shrink-0 gap-2">
                      <MessageSquarePlus className="h-4 w-4" />
                      Responder
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-xl">
                    <DialogHeader>
                      <DialogTitle className="text-xl">Adicionar ao Conhecimento</DialogTitle>
                      <DialogDescription className="pt-2">
                        Ao responder, esta pergunta será removida desta lista e adicionada ao FAQ oficial e ao RAG da IA.
                      </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                      <div className="p-3 bg-muted rounded-lg border border-border">
                        <p className="text-sm font-medium text-muted-foreground mb-1">Pergunta do Usuário:</p>
                        <p className="text-base font-medium">"{q.canonical_question}"</p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="answer" className="text-sm font-semibold">Resposta Oficial</Label>
                        <Textarea
                          id="answer"
                          placeholder="Digite aqui a resposta que a IA deve fornecer..."
                          value={answer}
                          onChange={(e) => setAnswer(e.target.value)}
                          rows={5}
                          className="resize-none"
                        />
                      </div>
                    </div>

                    <DialogFooter>
                      <Button variant="outline" onClick={() => setAnswer("")}>Limpar</Button>
                      <Button
                        onClick={() => convertToFaq(q.id)}
                        disabled={converting === q.id}
                      >
                        {converting === q.id ? "Salvando…" : "Salvar no FAQ"}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardContent>
          </Card>
        ))}

        {filtered.length === 0 && (
          <Card className="border-dashed border-2 bg-transparent">
            <CardContent className="py-16 text-center">
              <div className="flex flex-col items-center gap-3">
                <HelpCircle className="h-10 w-10 text-muted-foreground/50" />
                <p className="text-muted-foreground text-lg">
                  {questions.length === 0
                    ? "Excelente! Nenhuma pergunta pendente."
                    : "Nenhum resultado para esta busca."}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </PageContainer>
  );
}

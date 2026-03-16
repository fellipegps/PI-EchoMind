"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Search, MessageSquarePlus, HelpCircle, Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { PageContainer } from "@/components/page-container";
import { Label } from "@/components/ui/label";
import { unansweredApi, faqApi, UnansweredResponse } from "@/lib/api";

export default function UnansweredQuestions() {
  const [questions, setQuestions] = useState<UnansweredResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [answerMap, setAnswerMap] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await unansweredApi.list();
      setQuestions(data.filter((q) => !q.resolved));
    } catch (error: any) {
      toast.error(error?.message || "Erro ao carregar perguntas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  const filtered = questions.filter((q) =>
    q.question.toLowerCase().includes(search.toLowerCase())
  );

  const convertToFaq = async (q: UnansweredResponse) => {
    const answer = answerMap[q.id]?.trim();
    if (!answer) {
      toast.error("Por favor, escreva uma resposta.");
      return;
    }
    setSaving(q.id);
    try {
      // 1. Create the FAQ
      await faqApi.create({
        question: q.question,
        answer,
        category: "Geral",
      });
      // 2. Mark as resolved
      await unansweredApi.resolve(q.id);
      // 3. Remove from local state
      setQuestions((prev) => prev.filter((item) => item.id !== q.id));
      setAnswerMap((prev) => {
        const copy = { ...prev };
        delete copy[q.id];
        return copy;
      });
      toast.success("Pergunta convertida em FAQ com sucesso!");
    } catch (error: any) {
      toast.error(error?.message || "Erro ao salvar FAQ.");
    } finally {
      setSaving(null);
    }
  };

  const resolveOnly = async (id: string) => {
    try {
      await unansweredApi.resolve(id);
      setQuestions((prev) => prev.filter((q) => q.id !== id));
      toast.success("Pergunta marcada como resolvida.");
    } catch (error: any) {
      toast.error(error?.message || "Erro ao resolver pergunta.");
    }
  };

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

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <div className="grid gap-4">
          {filtered.map((q) => {
            const formattedDate = new Date(q.created_at).toLocaleDateString("pt-BR");
            return (
              <Card key={q.id} className="border-border bg-card hover:shadow-sm transition-shadow">
                <CardContent className="px-4 py-3">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 flex-wrap">
                        <p className="text-lg font-semibold text-foreground">{q.question}</p>
                        <Badge variant="secondary" className="bg-primary/10 text-primary border-none">
                          Registrada em {formattedDate}
                        </Badge>
                      </div>
                    </div>

                    <div className="flex gap-2 shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground gap-1.5"
                        onClick={() => resolveOnly(q.id)}
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Ignorar
                      </Button>

                      <Dialog>
                        <DialogTrigger asChild>
                          <Button className="gap-2">
                            <MessageSquarePlus className="h-4 w-4" />
                            Responder
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-lg">
                          <DialogHeader>
                            <DialogTitle className="text-xl">Adicionar ao Conhecimento</DialogTitle>
                            <DialogDescription className="pt-2">
                              Ao responder, esta pergunta será adicionada ao FAQ oficial e removida desta lista.
                            </DialogDescription>
                          </DialogHeader>

                          <div className="space-y-4 py-4">
                            <div className="p-3 bg-muted rounded-lg border border-border">
                              <p className="text-sm font-medium text-muted-foreground mb-1">Pergunta do Usuário:</p>
                              <p className="text-base font-medium">"{q.question}"</p>
                            </div>

                            <div className="space-y-2">
                              <Label htmlFor={`answer-${q.id}`} className="text-sm font-semibold">
                                Resposta Oficial <span className="text-destructive">*</span>
                              </Label>
                              <Textarea
                                id={`answer-${q.id}`}
                                placeholder="Digite aqui a resposta que a IA deve fornecer..."
                                value={answerMap[q.id] || ""}
                                onChange={(e) =>
                                  setAnswerMap((prev) => ({ ...prev, [q.id]: e.target.value }))
                                }
                                rows={5}
                                className="resize-none"
                              />
                            </div>
                          </div>

                          <DialogFooter>
                            <Button
                              variant="outline"
                              onClick={() => setAnswerMap((prev) => ({ ...prev, [q.id]: "" }))}
                            >
                              Limpar
                            </Button>
                            <Button
                              onClick={() => convertToFaq(q)}
                              disabled={saving === q.id}
                            >
                              {saving === q.id && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                              Salvar no FAQ
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}

          {filtered.length === 0 && (
            <Card className="border-dashed border-2 bg-transparent">
              <CardContent className="py-16 text-center">
                <div className="flex flex-col items-center gap-3">
                  <HelpCircle className="h-10 w-10 text-muted-foreground/50" />
                  <p className="text-muted-foreground text-lg">
                    {search
                      ? "Nenhuma pergunta encontrada para essa busca."
                      : "Nenhuma pergunta pendente. O agente está respondendo tudo! 🎉"
                    }
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </PageContainer>
  );
}

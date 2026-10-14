"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Search,
  MessageSquarePlus,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Ban,
  BookOpen,
  Pencil,
  Check,
  RotateCcw,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/page-header";
import { PageContainer } from "@/components/page-container";
import { Label } from "@/components/ui/label";
import { unansweredApi } from "@/lib/api";
import type { UnansweredQuestion } from "@/lib/api";

const REVIEW_REASON_LABELS: Record<string, string> = {
  abusive_language: "linguagem inadequada",
  possible_off_topic: "possivelmente fora do tema",
  external_link: "contém link externo",
  unclear: "pergunta pouco clara",
  mixed_variants: "variações diferentes precisam de avaliação",
};

export default function UnansweredQuestions() {
  const router = useRouter();
  const [questions, setQuestions] = useState<UnansweredQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<"pending" | "review" | "ignored">("pending");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [editedQuestion, setEditedQuestion] = useState("");
  const [converting, setConverting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  // ─── Carrega perguntas não respondidas do backend ─────────────────────────
  useEffect(() => {
    Promise.all([
      unansweredApi.list("pending"),
      unansweredApi.list("review"),
      unansweredApi.list("ignored"),
    ])
      .then(([pending, review, ignored]) => setQuestions([...pending, ...review, ...ignored]))
      .catch(() => toast.error("Erro ao carregar perguntas."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = questions.filter((q) =>
    q.triage_status === selectedStatus &&
    [q.canonical_question, ...q.similar_questions]
      .some((text) => text.toLowerCase().includes(search.toLowerCase()))
  );

  // ─── Remove imediatamente da lista (otimistic update) ─────────────────────
  const removeFromList = (id: string) =>
    setQuestions((prev) => prev.filter((q) => q.id !== id));

  // ─── Converter em FAQ oficial (visível no CRUD de FAQs) ───────────────────
  const convertToFaq = async (id: string) => {
    if (!answer.trim()) {
      toast.error("Por favor, escreva uma resposta.");
      return;
    }
    if (!editedQuestion.trim()) {
      toast.error("Por favor, verifique a pergunta.");
      return;
    }
    setConverting(id);
    try {
      await unansweredApi.convert(id, answer, editedQuestion.trim());
      removeFromList(id);
      setAnswer("");
      setEditedQuestion("");
      toast.success("FAQ criada! Redirecionando para a Base de Conhecimento…");
      router.push("/base-de-conhecimento");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao converter.");
    } finally {
      setConverting(null);
    }
  };

  // ─── Ignorar a pergunta e suas variações, sem reincidência ────────────────
  const ignoreQuestion = async (id: string) => {
    setDeleting(id);
    try {
      await unansweredApi.ignore(id);
      setQuestions((current) => current.map((question) =>
        question.id === id
          ? { ...question, triage_status: "ignored", triage_reason: "ignored_by_admin" }
          : question
      ));
      toast.success("Pergunta ignorada. Repetições iguais não voltarão à lista.");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao ignorar pergunta.");
    } finally {
      setDeleting(null);
    }
  };

  const approveQuestion = async (id: string) => {
    try {
      await unansweredApi.approve(id);
      setQuestions((current) => current.map((question) =>
        question.id === id
          ? { ...question, triage_status: "pending", triage_reason: null }
          : question
      ));
      toast.success("Pergunta enviada para pendentes.");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao aprovar pergunta.");
    }
  };

  const restoreQuestion = async (id: string) => {
    try {
      await unansweredApi.restore(id);
      setQuestions((current) => current.map((question) =>
        question.id === id
          ? { ...question, triage_status: "pending", triage_reason: "approved_by_admin" }
          : question
      ));
      toast.success("Pergunta restaurada para pendentes.");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao restaurar pergunta.");
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });

  if (loading) {
    return (
      <PageContainer variant="standard">
        <PageHeader title="Perguntas Não Respondidas" description="Analise o que o EchoMind ainda não sabe e transforme em conhecimento oficial." />
        <div role="status" aria-label="Carregando perguntas" className="space-y-4">
          <span className="sr-only">Carregando perguntas...</span>
          <Skeleton className="h-11 w-full max-w-md" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer variant="standard">
      <PageHeader title="Perguntas Não Respondidas" description="Analise o que o EchoMind ainda não sabe e transforme em conhecimento oficial." />

      <section aria-label="Triagem de perguntas" className="min-w-0 space-y-6">
        <div role="group" className="grid grid-cols-1 gap-2 sm:flex sm:flex-wrap" aria-label="Filtrar perguntas">
          <Button variant={selectedStatus === "pending" ? "default" : "outline"} onClick={() => setSelectedStatus("pending")} aria-pressed={selectedStatus === "pending"}>
            Pendentes ({questions.filter((q) => q.triage_status === "pending").length})
          </Button>
          <Button variant={selectedStatus === "review" ? "default" : "outline"} onClick={() => setSelectedStatus("review")} aria-pressed={selectedStatus === "review"}>
            Revisar ({questions.filter((q) => q.triage_status === "review").length})
          </Button>
          <Button variant={selectedStatus === "ignored" ? "default" : "outline"} onClick={() => setSelectedStatus("ignored")} aria-pressed={selectedStatus === "ignored"}>
            Ignoradas ({questions.filter((q) => q.triage_status === "ignored").length})
          </Button>
        </div>

        <div className="max-w-xl space-y-2">
          <Label htmlFor="triage-search">Buscar por pergunta ou variação</Label>
          <div className="relative">
            <Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="triage-search" placeholder="Pesquisar perguntas..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
          </div>
        </div>

        <div className="grid min-w-0 gap-4">
          {filtered.map((q) => (
            <article key={q.id} aria-labelledby={`triage-question-${q.id}`} className="min-w-0">
              <Card className="min-w-0">
                <CardContent className="p-4 md:p-6">
                  <div className="flex min-w-0 flex-col justify-between gap-6 xl:flex-row xl:items-start">
                    <div className="min-w-0 flex-1 space-y-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{q.count} {q.count === 1 ? "ocorrência" : "ocorrências"}</Badge>
                        <Badge variant={q.triage_status === "review" ? "warning" : q.triage_status === "ignored" ? "secondary" : "outline"}>
                          {q.triage_status === "pending" ? "Pendente" : q.triage_status === "review" ? "Em revisão" : "Ignorada"}
                        </Badge>
                      </div>
                      <h2 id={`triage-question-${q.id}`} className="text-lg leading-7 font-semibold [overflow-wrap:anywhere]">{q.canonical_question}</h2>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                        <span>Primeira vez: {formatDate(q.first_asked)}</span>
                        <span>Última vez: {formatDate(q.last_asked)}</span>
                      </div>
                      {q.triage_status === "review" && <p className="text-sm text-muted-foreground [overflow-wrap:anywhere]">Revisão necessária: {REVIEW_REASON_LABELS[q.triage_reason ?? ""] ?? "avaliação manual"}.</p>}
                      {q.triage_status === "ignored" && <p className="text-sm text-muted-foreground">{q.triage_reason === "ignored_by_admin" ? "Ignorada pelo administrador." : "Filtrada como mensagem sem pergunta aproveitável."}</p>}

                      {q.similar_questions.length > 0 && (
                        <div className="space-y-3">
                          <Button type="button" variant="ghost" aria-expanded={expanded === q.id} aria-controls={`triage-variants-${q.id}`} aria-describedby={`triage-question-${q.id}`} onClick={() => setExpanded(expanded === q.id ? null : q.id)} className="h-auto min-h-11 max-w-full justify-start px-3 py-2 text-left whitespace-normal text-primary">
                            {expanded === q.id ? <ChevronUp aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}
                            Ver {q.similar_questions.length} variações detectadas
                          </Button>
                          {expanded === q.id && (
                            <ul id={`triage-variants-${q.id}`} aria-label="Variações detectadas" className="space-y-3 rounded-lg border border-border bg-muted p-4 text-sm text-muted-foreground">
                              {q.similar_questions.map((sq, i) => <li key={i} className="[overflow-wrap:anywhere]">&quot;{sq}&quot;</li>)}
                            </ul>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex min-w-0 flex-wrap items-center gap-2 xl:max-w-64 xl:justify-end">
                      {q.triage_status === "ignored" && <Button variant="outline" aria-describedby={`triage-question-${q.id}`} onClick={() => restoreQuestion(q.id)}><RotateCcw aria-hidden="true" />Restaurar</Button>}
                      {q.triage_status === "review" && <Button variant="outline" aria-describedby={`triage-question-${q.id}`} onClick={() => approveQuestion(q.id)}><Check aria-hidden="true" />Enviar para pendentes</Button>}
                      {q.triage_status === "pending" && (
                        <Dialog onOpenChange={(open) => { if (open) { setEditedQuestion(q.canonical_question); } else { setAnswer(""); setEditedQuestion(""); } }}>
                          <DialogTrigger asChild><Button aria-describedby={`triage-question-${q.id}`}><MessageSquarePlus aria-hidden="true" />Responder</Button></DialogTrigger>
                          <DialogContent className="max-h-[calc(100dvh-2rem)] min-w-0 overflow-y-auto sm:max-w-xl">
                            <DialogHeader className="pr-8 text-left">
                              <DialogTitle className="text-xl leading-7">Criar FAQ Oficial</DialogTitle>
                              <DialogDescription>Revise a pergunta e escreva a resposta para criar uma <strong>FAQ oficial</strong> visível no painel de Base de Conhecimento.</DialogDescription>
                            </DialogHeader>
                            <div className="min-w-0 space-y-2">
                              <Label htmlFor={`question-${q.id}`}><Pencil aria-hidden="true" className="size-4" />Pergunta (editável)</Label>
                              <Input id={`question-${q.id}`} value={editedQuestion} onChange={(e) => setEditedQuestion(e.target.value)} placeholder="Pergunta do usuário..." />
                              {editedQuestion !== q.canonical_question && <p tabIndex={0} aria-label="Pergunta original" className="max-h-[20dvh] overflow-y-auto rounded-sm text-xs text-muted-foreground [overflow-wrap:anywhere] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">Original: &quot;{q.canonical_question}&quot;</p>}
                            </div>
                            <div className="min-w-0 space-y-2">
                              <Label htmlFor={`answer-${q.id}`}>Resposta</Label>
                              <Textarea id={`answer-${q.id}`} placeholder="Digite aqui a resposta que a IA deve fornecer..." value={answer} onChange={(e) => setAnswer(e.target.value)} rows={5} className="max-h-[25dvh] min-h-24 resize-none overflow-y-auto [field-sizing:fixed]" />
                            </div>
                            <p className="text-sm text-muted-foreground">A FAQ será indexada no RAG e ficará visível no painel de <span className="font-medium text-foreground">Base de Conhecimento</span>. Ideal para respostas que a instituição quer expor publicamente.</p>
                            <DialogFooter>
                              <Button variant="outline" onClick={() => { setAnswer(""); setEditedQuestion(q.canonical_question); }}>Limpar</Button>
                              <Button onClick={() => convertToFaq(q.id)} disabled={converting === q.id} aria-busy={converting === q.id}>
                                {converting === q.id ? <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : <BookOpen aria-hidden="true" />}
                                {converting === q.id ? "Salvando…" : "Salvar no FAQ"}
                              </Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      )}
                      {q.triage_status !== "ignored" && (
                        <AlertDialog>
                          <AlertDialogTrigger asChild><Button variant="outline" size="icon" aria-label="Ignorar pergunta" aria-describedby={`triage-question-${q.id}`} disabled={deleting === q.id}><Ban aria-hidden="true" /></Button></AlertDialogTrigger>
                          <AlertDialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto">
                            <AlertDialogHeader className="text-left">
                              <AlertDialogTitle>Ignorar pergunta?</AlertDialogTitle>
                              <AlertDialogDescription tabIndex={0} aria-label="Efeito de ignorar" className="max-h-[40dvh] overflow-y-auto rounded-sm [overflow-wrap:anywhere] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
                                A pergunta <span className="font-semibold text-foreground">&quot;{q.canonical_question}&quot;</span> deixará de aparecer nesta lista. Repetições iguais e as variações já identificadas também serão ignoradas.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter className="gap-2 sm:space-x-0">
                              <AlertDialogCancel>Cancelar</AlertDialogCancel>
                              <AlertDialogAction onClick={() => ignoreQuestion(q.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive hover:shadow-sm">Ignorar</AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </article>
          ))}
          {filtered.length === 0 && (
            <Card className="min-w-0 border-dashed">
              <CardContent className="flex flex-col items-center gap-3 px-4 py-12 text-center" role="status">
                <HelpCircle aria-hidden="true" className="size-10 text-muted-foreground" />
                <p className="text-base text-muted-foreground [overflow-wrap:anywhere]">{search ? "Nenhum resultado para esta busca." : selectedStatus === "pending" ? "Nenhuma pergunta pendente." : selectedStatus === "review" ? "Nenhuma pergunta para revisar." : "Nenhuma pergunta ignorada."}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </section>
    </PageContainer>
  );
}

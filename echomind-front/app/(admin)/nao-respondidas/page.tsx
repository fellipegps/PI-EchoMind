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
} from "lucide-react";
import { toast } from "sonner";
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
        <h1 className="text-3xl font-bold tracking-tight">
          Perguntas Não Respondidas
        </h1>
        <p className="text-muted-foreground mt-1 text-base">
          Analise o que o EchoMind ainda não sabe e transforme em
          conhecimento oficial.
        </p>
      </div>

      <div className="flex gap-2" aria-label="Filtrar perguntas">
        <Button
          variant={selectedStatus === "pending" ? "default" : "outline"}
          onClick={() => setSelectedStatus("pending")}
          aria-pressed={selectedStatus === "pending"}
        >
          Pendentes ({questions.filter((q) => q.triage_status === "pending").length})
        </Button>
        <Button
          variant={selectedStatus === "review" ? "default" : "outline"}
          onClick={() => setSelectedStatus("review")}
          aria-pressed={selectedStatus === "review"}
        >
          Revisar ({questions.filter((q) => q.triage_status === "review").length})
        </Button>
        <Button
          variant={selectedStatus === "ignored" ? "default" : "outline"}
          onClick={() => setSelectedStatus("ignored")}
          aria-pressed={selectedStatus === "ignored"}
        >
          Ignoradas ({questions.filter((q) => q.triage_status === "ignored").length})
        </Button>
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
          <Card
            key={q.id}
            className="border-border bg-card hover:shadow-sm transition-shadow"
          >
            <CardContent className="px-4 py-3">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                {/* ── Conteúdo da pergunta ── */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <p className="text-lg font-semibold text-foreground">
                      {q.canonical_question}
                    </p>
                    <Badge
                      variant="secondary"
                      className="bg-primary/10 text-primary border-none"
                    >
                      {q.count}{" "}
                      {q.count === 1 ? "ocorrência" : "ocorrências"}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-2 text-sm text-muted-foreground mt-2">
                    <span>Primeira vez: {formatDate(q.first_asked)}</span>
                    <span>•</span>
                    <span>Última vez: {formatDate(q.last_asked)}</span>
                  </div>
                  {q.triage_status === "review" && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      Revisão necessária: {REVIEW_REASON_LABELS[q.triage_reason ?? ""] ?? "avaliação manual"}.
                    </p>
                  )}
                  {q.triage_status === "ignored" && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      {q.triage_reason === "ignored_by_admin"
                        ? "Ignorada pelo administrador."
                        : "Filtrada como mensagem sem pergunta aproveitável."}
                    </p>
                  )}

                  {q.similar_questions.length > 0 && (
                    <div className="mt-4">
                      <button
                        onClick={() =>
                          setExpanded(expanded === q.id ? null : q.id)
                        }
                        className="text-sm text-primary flex items-center gap-1 font-medium hover:opacity-80"
                      >
                        {expanded === q.id ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                        Ver {q.similar_questions.length} variações detectadas
                      </button>

                      {expanded === q.id && (
                        <div className="mt-3 space-y-2 pl-4 border-l-2 border-primary/20 bg-muted/30 p-3 rounded-r-lg">
                          {q.similar_questions.map((sq, i) => (
                            <p
                              key={i}
                              className="text-sm text-muted-foreground italic"
                            >
                              &quot;{sq}&quot;
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* ── Ações ── */}
                <div className="flex items-center gap-2 shrink-0">
                  {q.triage_status === "ignored" && (
                    <Button variant="outline" onClick={() => restoreQuestion(q.id)}>
                      <RotateCcw className="h-4 w-4" /> Restaurar
                    </Button>
                  )}
                  {q.triage_status === "review" && (
                    <Button variant="outline" onClick={() => approveQuestion(q.id)}>
                      <Check className="h-4 w-4" /> Enviar para pendentes
                    </Button>
                  )}
                  {/* Botão Criar FAQ (Dialog direto, sem abas) */}
                  {q.triage_status === "pending" && <Dialog
                    onOpenChange={(open) => {
                      if (open) {
                        setEditedQuestion(q.canonical_question);
                      } else {
                        setAnswer("");
                        setEditedQuestion("");
                      }
                    }}
                  >
                    <DialogTrigger asChild>
                      <Button className="gap-2">
                        <MessageSquarePlus className="h-4 w-4" />
                        Responder
                      </Button>
                    </DialogTrigger>

                    <DialogContent className="sm:max-w-xl">
                      <DialogHeader>
                        <DialogTitle className="text-xl">
                          Criar FAQ Oficial
                        </DialogTitle>
                        <DialogDescription className="pt-2">
                          Revise a pergunta e escreva a resposta para criar
                          uma <strong>FAQ oficial</strong> visível no painel
                          de Base de Conhecimento.
                        </DialogDescription>
                      </DialogHeader>

                      {/* Campo editável da pergunta */}
                      <div className="space-y-2">
                        <Label
                          htmlFor={`question-${q.id}`}
                          className="text-sm font-semibold flex items-center gap-1"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Pergunta (editável)
                        </Label>
                        <Input
                          id={`question-${q.id}`}
                          value={editedQuestion}
                          onChange={(e) => setEditedQuestion(e.target.value)}
                          placeholder="Pergunta do usuário..."
                          className="bg-muted/40"
                        />
                        {editedQuestion !== q.canonical_question && (
                          <p className="text-xs text-muted-foreground">
                            Original:{" "}
                            <span className="italic">
                              &quot;{q.canonical_question}&quot;
                            </span>
                          </p>
                        )}
                      </div>

                      {/* Campo de resposta */}
                      <div className="space-y-2">
                        <Label
                          htmlFor={`answer-${q.id}`}
                          className="text-sm font-semibold"
                        >
                          Resposta
                        </Label>
                        <Textarea
                          id={`answer-${q.id}`}
                          placeholder="Digite aqui a resposta que a IA deve fornecer..."
                          value={answer}
                          onChange={(e) => setAnswer(e.target.value)}
                          rows={5}
                          className="resize-none"
                        />
                      </div>

                      <p className="text-sm text-muted-foreground">
                        A FAQ será indexada no RAG e ficará visível no
                        painel de{" "}
                        <span className="font-medium text-foreground">
                          Base de Conhecimento
                        </span>
                        . Ideal para respostas que a instituição quer expor
                        publicamente.
                      </p>

                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => {
                            setAnswer("");
                            setEditedQuestion(q.canonical_question);
                          }}
                        >
                          Limpar
                        </Button>
                        <Button
                          onClick={() => convertToFaq(q.id)}
                          disabled={converting === q.id}
                          className="gap-2"
                        >
                          <BookOpen className="h-4 w-4" />
                          {converting === q.id ? "Salvando…" : "Salvar no FAQ"}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>}

                  {/* Ignorar com confirmação */}
                  {q.triage_status !== "ignored" && <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        aria-label="Ignorar pergunta"
                        disabled={deleting === q.id}
                      >
                        <Ban className="h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>

                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Ignorar pergunta?</AlertDialogTitle>
                        <AlertDialogDescription>
                          A pergunta{" "}
                          <span className="font-semibold text-foreground">
                            &quot;{q.canonical_question}&quot;
                          </span>{" "}
                          deixará de aparecer nesta lista. Repetições iguais e
                          as variações já identificadas também serão ignoradas.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancelar</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => ignoreQuestion(q.id)}
                          className="bg-destructive text-destructive-foreground hover:bg-destructive/90 text-white"
                        >
                          Ignorar
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>}
                </div>
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
                  {search
                    ? "Nenhum resultado para esta busca."
                    : selectedStatus === "pending"
                      ? "Nenhuma pergunta pendente."
                      : selectedStatus === "review"
                        ? "Nenhuma pergunta para revisar."
                        : "Nenhuma pergunta ignorada."}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </PageContainer>
  );
}

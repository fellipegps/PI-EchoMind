"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Search, MessageSquarePlus, ChevronDown, ChevronUp, HelpCircle } from "lucide-react";
import { toast } from "sonner";
import { PageContainer } from "@/components/page-container";
import { Label } from "@/components/ui/label";

// Dados mockados apenas para visualização no front-end
const INITIAL_MOCK_DATA = [
  {
    id: "1",
    question: "Onde fica o bloco de odontologia?",
    count: 12,
    firstAsked: "12/03/2026",
    lastAsked: "hoje",
    similarQuestions: ["como chego na odonto", "bloco de odontologia localização"]
  },
  {
    id: "2",
    question: "Quais os documentos para o FIES?",
    count: 8,
    firstAsked: "10/03/2026",
    lastAsked: "ontem",
    similarQuestions: ["lista documentos fies", "o que levar pro fies"]
  }
];

export default function UnansweredQuestions() {
  const [questions, setQuestions] = useState(INITIAL_MOCK_DATA);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");

  const filtered = questions.filter((q) => 
    q.question.toLowerCase().includes(search.toLowerCase())
  );

  const convertToFaq = (id: string) => {
    if (!answer.trim()) {
      toast.error("Por favor, escreva uma resposta.");
      return;
    }
    // Remove da lista local para simular a conversão
    setQuestions(questions.filter((q) => q.id !== id));
    setAnswer("");
    toast.success("Resposta convertida em FAQ oficial com sucesso!");
  };

  return (
    <PageContainer className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Perguntas Não Respondidas</h1>
        <p className="text-muted-foreground mt-1 text-base">
          Analise o que o EchoMind ainda não sabe e transforme em conhecimento oficial.
        </p>
      </div>

      {/* Busca */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input 
          placeholder="Pesquisar perguntas..." 
          value={search} 
          onChange={(e) => setSearch(e.target.value)} 
          className="pl-10 bg-card border-border" 
        />
      </div>

      {/* Lista de Perguntas */}
      <div className="grid gap-4">
        {filtered.map((q) => (
          <Card key={q.id} className="border-border bg-card hover:shadow-sm transition-shadow">
            <CardContent className="px-4 py-3">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <p className="text-lg font-semibold text-foreground">{q.question}</p>
                    <Badge variant="secondary" className="bg-primary/10 text-primary border-none">
                      {q.count} ocorrências
                    </Badge>
                  </div>
                  
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mt-2">
                    <span>Primeira vez: {q.firstAsked}</span>
                    <span>•</span>
                    <span>Última vez: {q.lastAsked}</span>
                  </div>

                  {/* Perguntas Similares (Expansível) */}
                  {q.similarQuestions.length > 0 && (
                    <div className="mt-4">
                      <button
                        onClick={() => setExpanded(expanded === q.id ? null : q.id)}
                        className="text-sm text-primary flex items-center gap-1 font-medium hover:opacity-80"
                      >
                        {expanded === q.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        Ver {q.similarQuestions.length} variações detectadas
                      </button>
                      
                      {expanded === q.id && (
                        <div className="mt-3 space-y-2 pl-4 border-l-2 border-primary/20 bg-muted/30 p-3 rounded-r-lg">
                          {q.similarQuestions.map((sq, i) => (
                            <p key={i} className="text-sm text-muted-foreground italic">"{sq}"</p>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Ação de Responder */}
                <Dialog>
                  <DialogTrigger asChild>
                    <Button className="shrink-0 gap-2">
                      <MessageSquarePlus className="h-4 w-4" />
                      Responder
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-131.25">
                    <DialogHeader>
                      <DialogTitle className="text-xl">Adicionar ao Conhecimento</DialogTitle>
                      <DialogDescription className="pt-2">
                        Ao responder, esta pergunta e suas variações serão removidas desta lista e adicionadas ao FAQ oficial.
                      </DialogDescription>
                    </DialogHeader>
                    
                    <div className="space-y-4 py-4">
                      <div className="p-3 bg-muted rounded-lg border border-border">
                        <p className="text-sm font-medium text-muted-foreground mb-1">Pergunta do Usuário:</p>
                        <p className="text-base font-medium">"{q.question}"</p>
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
                      <Button onClick={() => convertToFaq(q.id)}>Salvar no FAQ</Button>
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
                <p className="text-muted-foreground text-lg">Excelente! Nenhuma pergunta pendente encontrada.</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </PageContainer>
  );
}


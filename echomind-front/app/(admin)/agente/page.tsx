"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Send, Bot, User, Loader2, Eraser, MessageSquareDashed } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/page-header";
import { PageContainer } from "@/components/page-container";
import { streamChat } from "@/lib/api";
import { supabase } from "@/lib/supabase";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const userFriendlyError = (err: Error) => {
  if (err.message.toLowerCase().includes("docker")) {
    return "A IA não retornou resposta. Verifique a conexão com o servidor.";
  }
  return err.message;
};

export default function ChatbotTest() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [tenantId, setTenantId] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  // Controla se o primeiro token já foi inserido como nova mensagem
  const firstTokenRef = useRef(true);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setTenantId(data.user?.id ?? "");
    });
  }, []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading || !tenantId) return;

    setInput("");
    firstTokenRef.current = true;

    // Adiciona apenas a mensagem do usuário — sem mensagem vazia do assistente
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    await streamChat(
      text,
      tenantId,
      // onToken: ignora tokens vazios; no primeiro token real, cria a mensagem
      // do assistente; nos seguintes, acumula no último item
      (token) => {
        if (!token) return;
        if (firstTokenRef.current) {
          firstTokenRef.current = false;
          setMessages((prev) => [...prev, { role: "assistant", content: token }]);
        } else {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              role: "assistant",
              content: updated[updated.length - 1].content + token,
            };
            return updated;
          });
        }
      },
      // onDone: stream chegou com conteúdo — apenas encerra o loading
      () => {
        setLoading(false);
      },
      // onError: stream vazio, erro HTTP, rede offline, etc.
      // Mostra no toast (não polui o chat com mensagem de erro)
      (err) => {
        toast.error(userFriendlyError(err) ?? "Erro ao conectar com a IA.", {
          duration: 6000,
        });
        setLoading(false);
      }
    );
  };

  const clearChat = () => {
    setMessages([]);
    toast.success("Conversa reiniciada");
  };

  // A última mensagem é do assistente E ainda está chegando tokens
  const isStreaming =
    loading &&
    messages.length > 0 &&
    messages[messages.length - 1].role === "assistant";

  // Ainda não chegou nenhum token (loading mas sem mensagem do assistente ainda)
  const isWaiting =
    loading &&
    (messages.length === 0 || messages[messages.length - 1].role === "user");

  return (
    <PageContainer>
      <PageHeader title="Testar Agente" description="Valide as respostas da sua IA em tempo real" actions={
        <Button variant="outline" size="sm" onClick={clearChat} className="gap-2">
          <Eraser className="h-4 w-4" aria-hidden="true" />
          Limpar
        </Button>
      } />

      <Card className="h-[min(680px,calc(100dvh-12rem))] min-h-[420px] gap-0 overflow-hidden pb-0">
        {/* shrink-0 garante que o header mantenha seu tamanho original */}
        <CardHeader className="shrink-0 gap-0 border-b px-4 [.border-b]:pb-5 md:px-6">
          <div className="flex items-start gap-3">
            <div className="shrink-0 rounded-lg bg-primary/10 p-2.5">
              <Bot className="h-5 w-5 text-primary" aria-hidden="true" />
            </div>
            <div>
              <CardTitle><h2 className="text-lg">Chatbot de Teste</h2></CardTitle>
              <CardDescription className="mt-1">
                O agente responderá conforme as informações da Base de Conhecimento
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        {/* flex-1 e overflow-hidden aqui são essenciais para conter o scroll interno */}
        <CardContent className="flex min-h-0 flex-1 flex-col overflow-hidden p-0">
          <div
            ref={scrollRef}
            role="log"
            aria-label="Conversa de teste"
            aria-live="polite"
            aria-relevant="additions"
            tabIndex={0}
            className="min-h-0 flex-1 space-y-5 overflow-x-hidden overflow-y-auto scroll-smooth bg-muted/20 p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring motion-reduce:scroll-auto md:p-6"
          >
            {messages.length === 0 && !loading && (
              <div className="flex h-full flex-col items-center justify-center space-y-3 text-center">
                <div className="rounded-2xl border bg-card p-4 text-primary">
                  <MessageSquareDashed className="h-7 w-7" aria-hidden="true" />
                </div>
                <p className="text-sm font-medium">Nenhuma mensagem enviada ainda.</p>
                <p className="max-w-sm text-sm text-muted-foreground">Envie uma pergunta para testar as respostas da sua base de conhecimento.</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex min-w-0 gap-2 md:gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                    <Bot className="h-4 w-4 text-primary" aria-hidden="true" />
                  </div>
                )}

                <div
                  className={`min-w-0 max-w-[calc(100%-2.5rem)] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 [overflow-wrap:anywhere] md:max-w-[80%] ${msg.role === "user"
                      ? "bg-primary text-primary-foreground rounded-tr-none"
                      : "bg-muted border border-border rounded-tl-none"
                    }`}
                >
                  <span className="sr-only">{msg.role === "user" ? "Você: " : "Agente: "}</span>
                  {msg.content}
                  {isStreaming && i === messages.length - 1 && (
                    <span aria-hidden="true" className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-current align-middle motion-reduce:animate-none" />
                  )}
                </div>

                {msg.role === "user" && (
                  <div className="shrink-0 h-8 w-8 rounded-full bg-accent flex items-center justify-center border border-border">
                    <User className="h-4 w-4 text-accent-foreground" aria-hidden="true" />
                  </div>
                )}
              </div>
            ))}

            {isWaiting && (
              <div className="flex items-start justify-start gap-3">
                <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                  <Bot className="h-4 w-4 text-primary" aria-hidden="true" />
                </div>
                <div className="flex items-center gap-2 rounded-2xl rounded-tl-none border bg-muted px-4 py-3 text-sm text-muted-foreground">
                  <Loader2 aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin motion-reduce:animate-none" />
                  Preparando resposta…
                </div>
              </div>
            )}
          </div>

          {/* shrink-0 aqui impede que o campo de input "suma" quando houver muitas mensagens */}
          <div className="shrink-0 space-y-2 border-t bg-card p-4 md:px-6">
            <Label htmlFor="agent-message">Mensagem para o agente</Label>
            <div className="mx-auto flex max-w-4xl gap-2">
              <Input
                id="agent-message"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
                placeholder="Pergunte algo ao seu agente..."
                disabled={loading}
                className="h-11 min-w-0 bg-background"
              />
              <Button
                onClick={sendMessage}
                disabled={loading || !input.trim() || !tenantId}
                aria-label="Enviar mensagem"
                aria-busy={loading}
                className="h-11 w-11 shrink-0"
              >
                {loading ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin motion-reduce:animate-none" />
                ) : (
                  <Send aria-hidden="true" className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p role="status" className="text-xs text-muted-foreground">
              {isWaiting ? "Aguardando a primeira resposta do agente." : isStreaming ? "Recebendo resposta…" : "Enter para enviar. As respostas usam a base de conhecimento atual."}
            </p>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}

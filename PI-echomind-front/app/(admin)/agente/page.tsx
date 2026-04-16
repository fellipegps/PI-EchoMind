"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Send, Bot, User, Loader2, Eraser, MessageSquareDashed } from "lucide-react";
import { toast } from "sonner";
import { PageContainer } from "@/components/page-container";
import { streamChat } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatbotTest() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Controla se o primeiro token já foi inserido como nova mensagem
  const firstTokenRef = useRef(true);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    firstTokenRef.current = true;

    // Adiciona apenas a mensagem do usuário — sem mensagem vazia do assistente
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    await streamChat(
      text,
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
        toast.error(err.message ?? "Erro ao conectar com a IA.", {
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
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Testar Agente</h1>
          <p className="text-muted-foreground mt-1">Valide as respostas da sua IA em tempo real</p>
        </div>
        <Button variant="outline" size="sm" onClick={clearChat} className="gap-2">
          <Eraser className="h-4 w-4" />
          Limpar
        </Button>
      </div>

      <Card className="border-border bg-card pb-0 pt-4 flex flex-col h-[600px] overflow-hidden">
        {/* shrink-0 garante que o header mantenha seu tamanho original */}
        <CardHeader className="border-b [.border-b]:pb-4 gap-0 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">Chatbot de Teste</CardTitle>
              <CardDescription>
                O agente responderá conforme as informações da Base de Conhecimento
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        {/* flex-1 e overflow-hidden aqui são essenciais para conter o scroll interno */}
        <CardContent className="flex-1 flex flex-col p-0 bg-card/50 overflow-hidden">
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-border scroll-smooth"
          >
            {messages.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-3 opacity-40">
                <div className="p-4 rounded-full bg-muted">
                  <MessageSquareDashed className="h-10 w-10" />
                </div>
                <p className="text-sm font-medium">Nenhuma mensagem enviada ainda.</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}

                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-sm whitespace-pre-wrap ${msg.role === "user"
                      ? "bg-primary text-primary-foreground rounded-tr-none"
                      : "bg-muted border border-border rounded-tl-none"
                    }`}
                >
                  {msg.content}
                  {isStreaming && i === messages.length - 1 && (
                    <span className="inline-block w-0.5 h-3.5 bg-current ml-0.5 animate-pulse align-middle" />
                  )}
                </div>

                {msg.role === "user" && (
                  <div className="shrink-0 h-8 w-8 rounded-full bg-accent flex items-center justify-center border border-border">
                    <User className="h-4 w-4 text-accent-foreground" />
                  </div>
                )}
              </div>
            ))}

            {isWaiting && (
              <div className="flex gap-3 justify-start animate-in fade-in duration-300">
                <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-muted border border-border rounded-2xl rounded-tl-none px-4 py-3 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}
          </div>

          {/* shrink-0 aqui impede que o campo de input "suma" quando houver muitas mensagens */}
          <div className="p-4 bg-background border-t shrink-0">
            <div className="flex gap-3 max-w-4xl mx-auto">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
                placeholder="Pergunte algo ao seu agente..."
                disabled={loading}
                className="bg-muted/50 border-border focus-visible:ring-primary h-11"
              />
              <Button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="h-11 px-6 shadow-md hover:shadow-lg transition-all"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}

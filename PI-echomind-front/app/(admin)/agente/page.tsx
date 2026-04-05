"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle, 
  CardDescription 
} from "@/components/ui/card";

import { 
  Send, 
  Bot, 
  User, 
  Loader2, 
  Eraser, 
  MessageSquareDashed, 
} from "lucide-react";
import { toast } from "sonner";
import { PageContainer } from "@/components/page-container";

/**
 * COMO FUNCIONA A SIMULAÇÃO DE CHAT (FAKE CONVERSATION):
 * * 1. ESTADO DE MENSAGENS (messages): 
 * As mensagens são armazenadas em um array de objetos [{ role, content }].
 * - 'user': Mensagens que você digita.
 * - 'assistant': Respostas automáticas do robô.
 * * 2. FLUXO DE ENVIO (sendMessage):
 * - Primeiro, adicionamos a mensagem do usuário ao array instantaneamente.
 * - Ativamos o estado 'loading' para exibir o ícone de carregamento (Loader2).
 * - Usamos um 'setTimeout' de 1000ms (1 segundo) para simular o tempo de 
 * processamento de uma IA real.
 * * 3. RESPOSTA DINÂMICA (Mock Response):
 * - Após 1 segundo, injetamos a resposta do 'assistant' no array.
 * - Desativamos o 'loading' para remover o ícone de espera e mostrar o balão.
 * * 4. AUTO-SCROLL (useEffect):
 * - Sempre que o array de mensagens muda ou o carregamento é ativado, o 
 * useEffect detecta a mudança e move a barra de rolagem da 'div' de 
 * mensagens para o final (scrollTop = scrollHeight).
 * * 5. LIMPEZA (clearChat):
 * - Simplesmente redefine o array de mensagens para vazio [], limpando a tela.
 */

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatbotTest() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { 
          role: "assistant", 
          content: `Esta é uma resposta de teste para: "${userMsg}". Agora usando ícones oficiais da Lucide!` 
        },
      ]);
      setLoading(false);
    }, 1000);
  };

  const clearChat = () => {
    setMessages([]);
    toast.success("Conversa reiniciada");
  };

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

      <Card className="border-border bg-card pb-0 pt-4 flex flex-col h-150 overflow-hidden">
        <CardHeader className="border-b [.border-b]:pb-4 gap-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">Chatbot de Teste</CardTitle>
              <CardDescription>O agente responderá conforme o informações fornecidas</CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col p-0 bg-card/50">
          <div 
            ref={scrollRef} 
            className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-border"
          >
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-3 opacity-40">
                <div className="p-4 rounded-full bg-muted">
                    {/* Ícone oficial substituído aqui */}
                    <MessageSquareDashed className="h-10 w-10" />
                </div>
                <p className="text-sm font-medium">Nenhuma mensagem enviada ainda.</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "assistant" && (
                  <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                
                <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                  msg.role === "user" 
                    ? "bg-primary text-primary-foreground rounded-tr-none" 
                    : "bg-muted border border-border rounded-tl-none"
                }`}>
                  {msg.content}
                </div>

                {msg.role === "user" && (
                  <div className="shrink-0 h-8 w-8 rounded-full bg-accent flex items-center justify-center border border-border">
                    <User className="h-4 w-4 text-accent-foreground" />
                  </div>
                )}
              </div>
            ))}
            
            {loading && (
              <div className="flex gap-3 justify-start animate-in fade-in duration-300">
                <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-muted border border-border rounded-2xl rounded-tl-none px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
          </div>

          <div className="p-4 bg-background border-t">
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
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Send, Bot, User, Loader2, Eraser, MessageSquareDashed, Wifi, WifiOff } from "lucide-react";
import { toast } from "sonner";
import { PageContainer } from "@/components/page-container";
import { faqApi } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatbotTest() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const data = await faqApi.ask(text);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer },
      ]);
      setIsOnline(true);
    } catch (error: any) {
      setIsOnline(false);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "⚠️ Não consegui me conectar ao servidor. Verifique se o backend está rodando.",
        },
      ]);
      toast.error(error?.message || "Erro ao conectar ao agente.");
    } finally {
      setLoading(false);
    }
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
          <p className="text-muted-foreground mt-1">Valide as respostas da IA em tempo real</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {isOnline
              ? <><Wifi className="h-3.5 w-3.5 text-green-500" /> <span className="text-green-500">Conectado</span></>
              : <><WifiOff className="h-3.5 w-3.5 text-destructive" /> <span className="text-destructive">Sem conexão</span></>
            }
          </div>
          <Button variant="outline" size="sm" onClick={clearChat} className="gap-2">
            <Eraser className="h-4 w-4" />Limpar
          </Button>
        </div>
      </div>

      <Card className="border-border bg-card pb-0 pt-4 flex flex-col h-[600px] overflow-hidden">
        <CardHeader className="border-b pb-4 gap-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">EchoMind</CardTitle>
              <CardDescription>Respondendo com base nas FAQs cadastradas</CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col p-0 bg-card/50 overflow-hidden">
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-6 space-y-6"
          >
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-3 opacity-40">
                <div className="p-4 rounded-full bg-muted">
                  <MessageSquareDashed className="h-10 w-10" />
                </div>
                <p className="text-sm font-medium">Faça uma pergunta para testar o agente.</p>
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
                placeholder="Pergunte algo ao agente..."
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

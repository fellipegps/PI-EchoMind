"use client";

import React, { useEffect, useState } from "react";
import { MessageCircle, MessageCircleQuestion, Clock } from "lucide-react";
import { 
  LineChart, Line, BarChart, Bar, XAxis, YAxis, 
  CartesianGrid, Tooltip, ResponsiveContainer 
} from "recharts";
import { 
  Card, CardContent, CardDescription, CardHeader, CardTitle 
} from "@/components/ui/card";
import { PageContainer } from "@/components/page-container";

const DASHBOARD_DATA = {
  totalQuestions: 1284,
  unansweredQuestions: 12,
  avgResponseTime: "1.2s",
  dailyInteractions: [
    { date: "01/02", count: 45 },
    { date: "02/02", count: 52 },
    { date: "03/02", count: 38 },
    { date: "04/02", count: 65 },
    { date: "05/02", count: 48 },
    { date: "06/02", count: 70 },
    { date: "07/02", count: 61 },
  ],
  topFAQs: [
    { question: "Resetar senha", count: 145 },
    { question: "Planos e Preços", count: 120 },
    { question: "Suporte técnico", count: 98 },
    { question: "Integração API", count: 75 },
    { question: "Cancelamento", count: 42 },
  ],
};

export default function DashboardPage() {
  const [mounted, setMounted] = useState(false);

  // Essencial para evitar erro de hidratação com Recharts no Next.js
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <PageContainer>
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard de Insights</h1>
        <p className="text-muted-foreground mt-1">Visão geral das interações com o Agente de IA</p>
      </div>

      {/* Cards de Métricas */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-border bg-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total de Perguntas</p>
                <p className="text-3xl font-bold">{DASHBOARD_DATA.totalQuestions.toLocaleString()}</p>
              </div>
              <div className="p-3 rounded-xl bg-primary/10">
                <MessageCircle className="h-6 w-6 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Sem Resposta</p>
                <p className="text-3xl font-bold">{DASHBOARD_DATA.unansweredQuestions}</p>
              </div>
              <div className="p-3 rounded-xl bg-destructive/10">
                <MessageCircleQuestion className="h-6 w-6 text-destructive" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Tempo Médio</p>
                <p className="text-3xl font-bold">{DASHBOARD_DATA.avgResponseTime}</p>
              </div>
              <div className="p-3 rounded-xl bg-accent">
                <Clock className="h-6 w-6 text-accent-foreground" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Seção de Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Gráfico de Linha - Usa var(--chart-1) */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-lg">Interações por Dia</CardTitle>
            <CardDescription>Volume usando cores do tema</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-75 w-full pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={DASHBOARD_DATA.dailyInteractions}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.5} />
                  <XAxis 
                    dataKey="date" 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} 
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} 
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--popover)', 
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)',
                      color: 'var(--popover-foreground)'
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="count" 
                    stroke="var(--chart-1)" 
                    strokeWidth={3} 
                    dot={{ fill: 'var(--chart-1)', strokeWidth: 2, r: 4 }} 
                    activeDot={{ r: 6, strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Gráfico de Barra - Usa var(--chart-2) */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-lg">FAQs Mais Consultadas</CardTitle>
            <CardDescription>Comparativo visual</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-75 w-full pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={DASHBOARD_DATA.topFAQs} layout="vertical" margin={{ left: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" opacity={0.5} />
                  <XAxis type="number" hide />
                  <YAxis 
                    dataKey="question" 
                    type="category" 
                    axisLine={false}
                    tickLine={false}
                    fontSize={12}
                    tick={{ fill: 'var(--muted-foreground)' }}
                  />
                  <Tooltip 
                    cursor={{ fill: 'var(--muted)', opacity: 0.4 }}
                    contentStyle={{ 
                      backgroundColor: 'var(--popover)', 
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)'
                    }}
                  />
                  <Bar 
                    dataKey="count" 
                    fill="var(--chart-2)" 
                    radius={[0, 4, 4, 0]} 
                    barSize={20}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

      </div>
    </PageContainer>
  );
}
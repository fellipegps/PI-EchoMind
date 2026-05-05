"use client";

import React, { useEffect, useState } from "react";
import { MessageCircle, MessageCircleQuestion, Clock } from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/page-container";
import { dashboardApi } from "@/lib/api";
import type { DashboardData } from "@/lib/api";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi
      .get()
      .then(setData)
      .catch(() => {
        // fallback visual para quando o backend ainda não tem dados
        setData({
          total_questions: 0,
          unanswered_questions: 0,
          avg_response_time: "—",
          daily_interactions: [],
          top_faqs: [],
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <PageContainer>
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
        <Skeleton className="h-72 mt-6" />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard de Insights</h1>
        <p className="text-muted-foreground mt-1">Visão geral das interações com o Agente de IA</p>
      </div>

      {/* ── Métricas ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-border bg-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total de Perguntas</p>
                <p className="text-3xl font-bold mt-1">{data?.total_questions.toLocaleString("pt-BR")}</p>
              </div>
              <div className="p-3 rounded-full bg-primary/10">
                <MessageCircle className="h-6 w-6 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Não Respondidas</p>
                <p className="text-3xl font-bold mt-1">{data?.unanswered_questions}</p>
              </div>
              <div className="p-3 rounded-full bg-destructive/10">
                <MessageCircleQuestion className="h-6 w-6 text-destructive" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Tempo Médio de Resposta</p>
                <p className="text-3xl font-bold mt-1">{data?.avg_response_time}</p>
              </div>
              <div className="p-3 rounded-full bg-green-500/10">
                <Clock className="h-6 w-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Gráficos ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle>Interações dos Últimos 7 Dias</CardTitle>
            <CardDescription>Volume diário de perguntas recebidas</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={data?.daily_interactions ?? []}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="date" className="text-xs" />
                <YAxis className="text-xs" />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#01a6fd" strokeWidth={2} dot={{ r: 4 }} name="Perguntas" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle>FAQs Mais Acessadas</CardTitle>
            <CardDescription>Perguntas com maior frequência de consulta</CardDescription>
          </CardHeader>
          <CardContent>
            {data?.top_faqs.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground text-sm">
                Nenhum dado disponível ainda.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={data?.top_faqs ?? []} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis type="number" className="text-xs" />
                  <YAxis
                    dataKey="question"
                    type="category"
                    width={120}
                    className="text-xs"
                    tickFormatter={(v: string) => v.length > 18 ? v.slice(0, 18) + "…" : v}
                  />
                  <Tooltip />
                  <Bar dataKey="count" fill="#01a6fd" radius={[0, 4, 4, 0]} name="Consultas" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}

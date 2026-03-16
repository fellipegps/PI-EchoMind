"use client";

import React, { useEffect, useState } from "react";
import { MessageCircle, MessageCircleQuestion, Clock, FileText, Loader2 } from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle
} from "@/components/ui/card";
import { PageContainer } from "@/components/page-container";
import { metricsApi, MetricsOverview } from "@/lib/api";
import { toast } from "sonner";

const FALLBACK_DATA: MetricsOverview = {
  total_interactions: 0,
  unanswered_count: 0,
  total_faqs: 0,
  total_events: 0,
  daily_interactions: [],
  top_faqs: [],
};

export default function DashboardPage() {
  const [mounted, setMounted] = useState(false);
  const [data, setData] = useState<MetricsOverview>(FALLBACK_DATA);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setMounted(true);
    metricsApi.overview()
      .then(setData)
      .catch(() => toast.error("Não foi possível carregar as métricas."))
      .finally(() => setLoading(false));
  }, []);

  if (!mounted) return null;

  return (
    <PageContainer>
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard de Insights</h1>
        <p className="text-muted-foreground mt-1">Visão geral das interações com o Agente de IA</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <>
          {/* Metric Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card className="border-border bg-card">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Total de Interações</p>
                    <p className="text-3xl font-bold">{data.total_interactions.toLocaleString()}</p>
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
                    <p className="text-3xl font-bold">{data.unanswered_count}</p>
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
                    <p className="text-sm font-medium text-muted-foreground">FAQs Cadastradas</p>
                    <p className="text-3xl font-bold">{data.total_faqs}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-accent">
                    <FileText className="h-6 w-6 text-accent-foreground" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border bg-card">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Eventos Cadastrados</p>
                    <p className="text-3xl font-bold">{data.total_events}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-chart-3/10">
                    <Clock className="h-6 w-6 text-chart-3" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg">Interações por Dia</CardTitle>
                <CardDescription>Volume nos últimos dias</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64 w-full pt-4">
                  {data.daily_interactions.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={data.daily_interactions}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.5} />
                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }} />
                        <Tooltip contentStyle={{ backgroundColor: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--popover-foreground)' }} />
                        <Line type="monotone" dataKey="count" stroke="var(--chart-1)" strokeWidth={3} dot={{ fill: 'var(--chart-1)', strokeWidth: 2, r: 4 }} activeDot={{ r: 6, strokeWidth: 0 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                      Nenhuma interação registrada ainda.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-lg">FAQs Mais Consultadas</CardTitle>
                <CardDescription>Perguntas mais acessadas</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64 w-full pt-4">
                  {data.top_faqs.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.top_faqs} layout="vertical" margin={{ left: 40 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" opacity={0.5} />
                        <XAxis type="number" hide />
                        <YAxis dataKey="question" type="category" axisLine={false} tickLine={false} fontSize={12} tick={{ fill: 'var(--muted-foreground)' }} />
                        <Tooltip cursor={{ fill: 'var(--muted)', opacity: 0.4 }} contentStyle={{ backgroundColor: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }} />
                        <Bar dataKey="count" fill="var(--chart-2)" radius={[0, 4, 4, 0]} barSize={20} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                      Ainda sem dados de consultas.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </PageContainer>
  );
}

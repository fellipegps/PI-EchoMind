"use client";

import React, { useEffect, useState } from "react";
import { MessageCircle, MessageCircleQuestion, Clock, ThumbsUp } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { PageContainer } from "@/components/page-container";
import { dashboardApi } from "@/lib/api";
import type { DashboardData } from "@/lib/api";
import { RagMetricsSection } from "./rag-metrics-section";
import { MetricCard } from "./metric-card";
import { DashboardCharts } from "./dashboard-charts";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi
      .get()
      .then(setData)
      .catch(() => {
        // Política preexistente: falhas também usam zeros/listas vazias; não distinguem indisponibilidade.
        setData({
          total_questions: 0,
          unanswered_questions: 0,
          avg_response_time: "—",
          satisfaction_rate: 0,
          daily_interactions: [],
          top_faqs: [],
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader title="Dashboard de Insights" description="Visão geral das interações com o Agente de IA" />
        <div role="status" aria-label="Carregando indicadores do dashboard">
          <span className="sr-only">Carregando indicadores do dashboard...</span>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-40" />)}
          </div>
          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Skeleton className="h-96" /><Skeleton className="h-96" />
          </div>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader title="Dashboard de Insights" description="Visão geral das interações com o Agente de IA" />

      <div className="grid min-w-0 grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total de Perguntas" value={data?.total_questions.toLocaleString("pt-BR") ?? "0"} icon={MessageCircle} />
        <MetricCard label="Não Respondidas" value={data?.unanswered_questions.toLocaleString("pt-BR") ?? "0"} icon={MessageCircleQuestion} tone="destructive" />
        <MetricCard label="Tempo Médio de Resposta" value={data?.avg_response_time ?? "—"} icon={Clock} tone="success" />
        <MetricCard label="Satisfação" value={`${data?.satisfaction_rate.toLocaleString("pt-BR") ?? 0}%`} icon={ThumbsUp} />
      </div>

      <DashboardCharts daily_interactions={data?.daily_interactions ?? []} top_faqs={data?.top_faqs ?? []} />
      <RagMetricsSection />
    </PageContainer>
  );
}

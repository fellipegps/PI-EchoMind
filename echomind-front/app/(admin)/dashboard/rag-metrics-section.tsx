"use client";

import { useEffect, useState } from "react";
import { Activity, Database, Search, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardApi } from "@/lib/api";
import type { RagMetricsData } from "@/lib/api";


const SOURCE_LABELS: Array<[keyof RagMetricsData["source_types"], string]> = [
  ["faq", "FAQs"],
  ["event", "Eventos"],
  ["document_chunk", "Trechos de documentos"],
  ["document_parent", "Contextos expandidos"],
  ["other", "Outros"],
];

function formatNumber(value: number, maximumFractionDigits = 2) {
  return value.toLocaleString("pt-BR", { maximumFractionDigits });
}

export function RagMetricsSection() {
  const [data, setData] = useState<RagMetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const retry = async () => {
    setLoading(true);
    setFailed(false);
    try {
      setData(await dashboardApi.getRagMetrics(30));
      setFailed(false);
    } catch {
      setData(null);
      setFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    dashboardApi
      .getRagMetrics(30)
      .then((metrics) => {
        if (active) setData(metrics);
      })
      .catch(() => {
        if (active) setFailed(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <section aria-label="Métricas operacionais do RAG" role="status">
        <Skeleton className="h-8 w-56" />
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
        <span className="sr-only">Carregando métricas do RAG...</span>
      </section>
    );
  }

  if (failed) {
    return (
      <Card role="alert" className="border-destructive/40">
        <CardContent className="flex flex-col items-start gap-3 pt-6">
          <p className="font-medium">Não foi possível carregar as métricas do RAG.</p>
          <p className="text-sm text-muted-foreground">
            Os demais dados do dashboard continuam disponíveis.
          </p>
          <Button type="button" variant="outline" onClick={() => void retry()}>
            Tentar novamente
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data?.has_data) {
    return (
      <Card aria-label="Métricas operacionais do RAG">
        <CardHeader>
          <CardTitle>Saúde do RAG</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Nenhuma métrica operacional nos últimos 30 dias.
        </CardContent>
      </Card>
    );
  }

  const operationalCards = [
    {
      label: "Consultas",
      value: formatNumber(data.query_count, 0),
      icon: Activity,
    },
    {
      label: "Latência média do retrieval",
      value: `${formatNumber(data.retrieval.average_latency_ms)} ms`,
      icon: Search,
    },
    {
      label: "Resultados por consulta",
      value: formatNumber(data.average_retrieved_results),
      icon: Database,
    },
    {
      label: "Falhas operacionais",
      value: formatNumber(data.failure_count, 0),
      icon: TriangleAlert,
    },
  ];

  return (
    <section aria-labelledby="rag-metrics-title" className="space-y-4">
      <div>
        <h2 id="rag-metrics-title" className="text-2xl font-semibold tracking-tight">
          Saúde do RAG
        </h2>
        <p className="text-sm text-muted-foreground">
          Agregados operacionais dos últimos {data.period_days} dias, sem conteúdo de perguntas.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {operationalCards.map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardContent className="flex items-center justify-between pt-6">
              <div>
                <p className="text-sm text-muted-foreground">{label}</p>
                <p className="mt-1 text-2xl font-bold">{value}</p>
              </div>
              <Icon aria-hidden="true" className="h-5 w-5 text-primary" />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Status das operações</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {([
              ["Retrieval", data.retrieval],
              ["Ingestão", data.ingestion],
            ] as const).map(([label, operation]) => (
              <div key={label} className="grid grid-cols-4 gap-2 text-sm">
                <span className="font-medium">{label}</span>
                <span>Total: {operation.total}</span>
                <span>Sucesso: {operation.success}</span>
                <span>Erro: {operation.error}</span>
              </div>
            ))}
            <p className="text-sm text-muted-foreground">
              Latência média de ingestão: {formatNumber(data.ingestion.average_latency_ms)} ms
            </p>
            <p className="text-sm text-muted-foreground">
              Taxa sem resposta: {formatNumber(data.unanswered_rate)}%
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tipos de fonte recuperados</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
              {SOURCE_LABELS.map(([key, label]) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="font-medium">{formatNumber(data.source_types[key], 0)}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

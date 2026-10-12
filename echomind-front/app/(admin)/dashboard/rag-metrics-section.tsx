"use client";

import { useEffect, useState } from "react";
import { Activity, Database, Search, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardApi } from "@/lib/api";
import type { RagMetricsData } from "@/lib/api";
import { MetricCard } from "./metric-card";


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
        <Skeleton className="h-8 w-56 max-w-full" />
        <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
        <span className="sr-only">Carregando métricas do RAG...</span>
      </section>
    );
  }

  if (failed) {
    return (
      <Card role="alert" aria-label="Métricas operacionais do RAG" className="min-w-0 border-destructive">
        <CardContent className="flex flex-col items-start gap-3">
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
      <Card aria-label="Métricas operacionais do RAG" className="min-w-0">
        <CardHeader>
          <CardTitle><h2>Saúde do RAG</h2></CardTitle>
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

      <div className="grid min-w-0 grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        {operationalCards.map(({ label, value, icon }) => (
          <MetricCard key={label} label={label} value={value} icon={icon} tone={label === "Falhas operacionais" ? "destructive" : "primary"} />
        ))}
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle><h3>Status das operações</h3></CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {([
              ["Retrieval", data.retrieval],
              ["Ingestão", data.ingestion],
            ] as const).map(([label, operation]) => (
              <div key={label} className="space-y-3 border-b border-border pb-4 text-sm [overflow-wrap:anywhere]">
                <h4 className="font-medium">{label}</h4>
                <dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {([
                    ["Total", operation.total],
                    ["Sucesso", operation.success],
                    ["Erro", operation.error],
                  ] as const).map(([name, value]) => (
                    <div key={name} className="min-w-0 rounded-lg bg-muted p-3">
                      <dt className="text-muted-foreground">{name}</dt>
                      <dd className="mt-1 font-semibold tabular-nums">{formatNumber(value, 0)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
            <p className="text-sm text-muted-foreground [overflow-wrap:anywhere]">
              Latência média de ingestão: {formatNumber(data.ingestion.average_latency_ms)} ms
            </p>
            <p className="text-sm text-muted-foreground [overflow-wrap:anywhere]">
              Taxa sem resposta: {formatNumber(data.unanswered_rate)}%
            </p>
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle><h3>Tipos de fonte recuperados</h3></CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
              {SOURCE_LABELS.map(([key, label]) => (
                <div key={key} className="grid grid-cols-2 gap-3 border-b border-border pb-3 text-sm last:border-0 last:pb-0 [overflow-wrap:anywhere]">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="text-right font-medium tabular-nums">{formatNumber(data.source_types[key], 0)}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

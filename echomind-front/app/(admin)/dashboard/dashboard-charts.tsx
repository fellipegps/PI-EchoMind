"use client";

import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { TooltipContentProps } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardData } from "@/lib/api";

const axis = { fill: "var(--muted-foreground)", fontSize: 12 };
const integer = (value: number) => value.toLocaleString("pt-BR");
const compact = (value: number) => value.toLocaleString("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

function ChartTooltip({ active, payload, label }: Pick<TooltipContentProps<number, string>, "active" | "payload" | "label">) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover p-3 text-sm text-popover-foreground shadow-md [overflow-wrap:anywhere]">
      <p className="mb-1 font-medium">{label}</p>
      {payload.map((entry) => (
        <p key={String(entry.dataKey)} className="tabular-nums">{entry.name}: {integer(Number(entry.value))}</p>
      ))}
    </div>
  );
}

const tooltipStyle = { width: "min(18rem, 100%)", zIndex: 10 };
const detailsClass = "rounded-lg text-sm [&_summary]:min-h-11 [&_summary]:cursor-pointer [&_summary]:content-center [&_summary]:rounded-md [&_summary]:text-primary [&_summary]:focus-visible:outline-2 [&_summary]:focus-visible:outline-offset-2 [&_summary]:focus-visible:outline-ring";

export function DashboardCharts({ daily_interactions, top_faqs }: Pick<DashboardData, "daily_interactions" | "top_faqs">) {
  return (
    <div className="grid min-w-0 grid-cols-1 gap-6 xl:grid-cols-2">
      <Card className="min-w-0">
        <CardHeader>
          <CardTitle><h2>Interações dos Últimos 7 Dias</h2></CardTitle>
          <CardDescription>Volume diário de perguntas recebidas</CardDescription>
        </CardHeader>
        <CardContent className="min-w-0 space-y-3">
          {daily_interactions.length === 0 ? (
            <EmptyChart />
          ) : (
            <>
              <div className="[&_[role=application]]:rounded-md [&_[role=application]]:focus-visible:outline-2 [&_[role=application]]:focus-visible:outline-offset-2 [&_[role=application]]:focus-visible:outline-ring">
                <ResponsiveContainer width="100%" height={250} minWidth={0}>
                  <LineChart data={daily_interactions} accessibilityLayer title="Interações diárias" desc="Use as setas para consultar os valores ou abra os dados abaixo." margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="date" tick={axis} stroke="var(--border)" tickLine={false} minTickGap={24} />
                    <YAxis tick={axis} stroke="var(--border)" tickLine={false} axisLine={false} width={48} allowDecimals={false} tickFormatter={compact} />
                    <Tooltip content={ChartTooltip} position={{ x: 0, y: 0 }} wrapperStyle={tooltipStyle} isAnimationActive={false} cursor={{ stroke: "var(--border)" }} />
                    <Line type="monotone" dataKey="count" stroke="var(--chart-1)" strokeWidth={2} dot={{ r: 4, fill: "var(--card)" }} activeDot={{ r: 5 }} name="Perguntas" isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <details className={detailsClass}>
                <summary>Ver dados das interações</summary>
                <dl className="mt-3 space-y-3">
                  {daily_interactions.map(({ date, count }, index) => (
                    <div key={`${date}-${index}`} className="grid grid-cols-2 gap-3 border-t border-border pt-3 [overflow-wrap:anywhere]">
                      <dt className="text-muted-foreground">{date}</dt><dd className="text-right tabular-nums">{integer(count)} perguntas</dd>
                    </div>
                  ))}
                </dl>
              </details>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="min-w-0">
        <CardHeader>
          <CardTitle><h2>FAQs Mais Acessadas</h2></CardTitle>
          <CardDescription>Perguntas com maior frequência de consulta</CardDescription>
        </CardHeader>
        <CardContent className="min-w-0 space-y-3">
          {top_faqs.length === 0 ? (
            <EmptyChart />
          ) : (
            <>
              <div className="[&_[role=application]]:rounded-md [&_[role=application]]:focus-visible:outline-2 [&_[role=application]]:focus-visible:outline-offset-2 [&_[role=application]]:focus-visible:outline-ring">
                <ResponsiveContainer width="100%" height={Math.max(250, top_faqs.length * 48)} minWidth={0}>
                  <BarChart data={top_faqs} layout="vertical" accessibilityLayer title="Consultas por FAQ" desc="Use as setas para consultar os valores ou abra as perguntas completas abaixo." margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                    <XAxis type="number" tick={axis} stroke="var(--border)" tickLine={false} allowDecimals={false} tickFormatter={compact} />
                    <YAxis dataKey="question" type="category" width={104} tick={axis} stroke="var(--border)" tickLine={false} axisLine={false} interval={0} tickFormatter={(v: string) => v.length > 14 ? `${v.slice(0, 14)}…` : v} />
                    <Tooltip content={ChartTooltip} position={{ x: 0, y: 0 }} wrapperStyle={tooltipStyle} isAnimationActive={false} cursor={{ fill: "var(--muted)" }} />
                    <Bar dataKey="count" fill="var(--chart-1)" radius={[0, 4, 4, 0]} maxBarSize={28} name="Consultas" isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <details className={detailsClass}>
                <summary>Ver perguntas completas e consultas</summary>
                <dl className="mt-3 space-y-3">
                  {top_faqs.map(({ question, count }, index) => (
                    <div key={`${question}-${index}`} className="space-y-1 border-t border-border pt-3 [overflow-wrap:anywhere]">
                      <dt>{question}</dt><dd className="font-medium text-muted-foreground tabular-nums">{integer(count)} consultas</dd>
                    </div>
                  ))}
                </dl>
              </details>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function EmptyChart() {
  return <p className="flex min-h-[250px] items-center justify-center text-center text-sm text-muted-foreground">Nenhum dado disponível ainda.</p>;
}

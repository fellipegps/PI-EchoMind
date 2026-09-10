import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const dashboardApiMock = vi.hoisted(() => ({
  getRagMetrics: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  dashboardApi: dashboardApiMock,
}));

import type { RagMetricsData } from "@/lib/api";
import { RagMetricsSection } from "./rag-metrics-section";


const metrics: RagMetricsData = {
  period_days: 30,
  start_date: "2026-08-09",
  end_date: "2026-09-07",
  has_data: true,
  query_count: 1234,
  query_error_count: 1,
  failure_count: 3,
  average_retrieved_results: 2.5,
  unanswered_rate: 4.25,
  retrieval: {
    total: 20,
    success: 19,
    error: 1,
    average_latency_ms: 12.5,
  },
  ingestion: {
    total: 5,
    success: 4,
    error: 1,
    average_latency_ms: 150.75,
  },
  source_types: {
    faq: 8,
    event: 3,
    document_chunk: 12,
    document_parent: 7,
    other: 0,
  },
  daily: [],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe("RagMetricsSection", () => {
  beforeEach(() => {
    dashboardApiMock.getRagMetrics.mockReset();
  });

  it("mostra loading enquanto consulta o período limitado", async () => {
    const pending = deferred<RagMetricsData>();
    dashboardApiMock.getRagMetrics.mockReturnValueOnce(pending.promise);

    render(<RagMetricsSection />);

    expect(screen.getByRole("status")).toHaveTextContent("Carregando métricas do RAG...");
    expect(dashboardApiMock.getRagMetrics).toHaveBeenCalledWith(30);
    pending.resolve(metrics);
    expect(await screen.findByText("1.234")).toBeInTheDocument();
  });

  it("trata o estado vazio sem inventar números", async () => {
    dashboardApiMock.getRagMetrics.mockResolvedValueOnce({
      ...metrics,
      has_data: false,
      query_count: 0,
    });

    render(<RagMetricsSection />);

    expect(
      await screen.findByText("Nenhuma métrica operacional nos últimos 30 dias.")
    ).toBeInTheDocument();
    expect(screen.queryByText("Resultados por consulta")).not.toBeInTheDocument();
  });

  it("mostra erro seguro e permite tentar novamente", async () => {
    const user = userEvent.setup();
    dashboardApiMock.getRagMetrics
      .mockRejectedValueOnce(new Error("segredo interno do banco"))
      .mockResolvedValueOnce(metrics);

    render(<RagMetricsSection />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Não foi possível carregar as métricas do RAG.");
    expect(alert).not.toHaveTextContent("segredo interno do banco");

    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    expect(await screen.findByText("1.234")).toBeInTheDocument();
    expect(dashboardApiMock.getRagMetrics).toHaveBeenCalledTimes(2);
  });

  it("apresenta volume, latências, status, taxa e tipos de fonte", async () => {
    dashboardApiMock.getRagMetrics.mockResolvedValueOnce(metrics);

    render(<RagMetricsSection />);

    expect(await screen.findByText("1.234")).toBeInTheDocument();
    expect(screen.getByText("12,5 ms")).toBeInTheDocument();
    expect(screen.getByText("2,5")).toBeInTheDocument();
    expect(screen.getByText("Falhas operacionais")).toBeInTheDocument();
    expect(screen.getByText("Taxa sem resposta: 4,25%")).toBeInTheDocument();
    expect(screen.getByText("Latência média de ingestão: 150,75 ms")).toBeInTheDocument();
    expect(screen.getByText("Contextos expandidos").nextElementSibling).toHaveTextContent("7");
    expect(screen.getByText("Retrieval").parentElement).toHaveTextContent(
      "Total: 20Sucesso: 19Erro: 1"
    );
  });
});

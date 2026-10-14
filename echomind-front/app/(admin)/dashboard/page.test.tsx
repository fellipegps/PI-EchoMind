import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ get: vi.fn(), getRagMetrics: vi.fn() }));
vi.mock("@/lib/api", () => ({ dashboardApi: api }));
// Chart geometry and tooltips are verified in the browser; jsdom has no layout.
vi.mock("recharts", async (importOriginal) => ({
  ...await importOriginal<typeof import("recharts")>(),
  ResponsiveContainer: () => null,
}));

import DashboardPage from "./page";

const question = "Como consultar os procedimentos institucionais de matrícula, transferência e bolsas de estudo para o próximo semestre?";
const dashboard = {
  total_questions: 1234567890,
  unanswered_questions: 12345,
  avg_response_time: "1,25 s",
  satisfaction_rate: 92.5,
  daily_interactions: [{ date: "12/10", count: 123456 }],
  top_faqs: [{ question, count: 12345 }],
};

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.get.mockResolvedValue(dashboard);
    api.getRagMetrics.mockResolvedValue({ has_data: false });
  });

  it("mantém os quatro indicadores, unidades, séries e acesso à FAQ completa", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    expect(await screen.findByText("1.234.567.890")).toBeInTheDocument();
    expect(screen.getByText("12.345")).toBeInTheDocument();
    expect(screen.getByText("1,25 s")).toBeInTheDocument();
    expect(screen.getByText("92,5%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "FAQs Mais Acessadas" })).toBeInTheDocument();
    const summary = screen.getByText("Ver perguntas completas e consultas");
    await user.click(summary);
    expect(summary.parentElement).toHaveAttribute("open");
    expect(screen.getByText(question)).toBeVisible();
    expect(screen.getByText("12.345 consultas")).toBeVisible();
    expect(screen.getByText("12/10")).toBeInTheDocument();
    expect(screen.getByText("123.456 perguntas")).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(api.getRagMetrics).toHaveBeenCalledWith(30);
  });

  it("preserva zeros/listas vazias na falha principal sem ocultar o estado RAG independente", async () => {
    api.get.mockRejectedValue(new Error("detalhe interno principal"));
    api.getRagMetrics.mockRejectedValue(new Error("detalhe interno RAG"));
    render(<DashboardPage />);
    expect(await screen.findByText("—")).toBeInTheDocument();
    expect(screen.getAllByText("0")).toHaveLength(2);
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getAllByText("Nenhum dado disponível ainda.")).toHaveLength(2);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar as métricas do RAG.");
    expect(screen.queryByText(/detalhe interno/)).not.toBeInTheDocument();
    expect(screen.queryByText("1.284")).not.toBeInTheDocument();
  });

  it("mantém os indicadores disponíveis durante carregamento e falha RAG", async () => {
    let reject!: (error: Error) => void;
    api.getRagMetrics.mockReturnValue(new Promise((_, rejectPromise) => { reject = rejectPromise; }));
    render(<DashboardPage />);
    expect(await screen.findByText("1.234.567.890")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Carregando métricas do RAG...");
    await act(async () => reject(new Error("interno")));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("1.234.567.890")).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledTimes(1);
  });
});

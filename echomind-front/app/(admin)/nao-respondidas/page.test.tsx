import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  approve: vi.fn(),
  ignore: vi.fn(),
  restore: vi.fn(),
  convert: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  unansweredApi: {
    list: mocks.list,
    approve: mocks.approve,
    ignore: mocks.ignore,
    restore: mocks.restore,
    convert: mocks.convert,
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import UnansweredQuestions from "./page";

const pending = {
  id: "pending-1",
  canonical_question: "Onde vejo minhas notas?",
  count: 2,
  first_asked: "2026-10-01T10:00:00Z",
  last_asked: "2026-10-02T10:00:00Z",
  similar_questions: [],
  triage_status: "pending",
  triage_reason: null,
};
const review = {
  ...pending,
  id: "review-1",
  canonical_question: "Que porra é o prazo de matrícula?",
  count: 1,
  triage_status: "review",
  triage_reason: "abusive_language",
};

describe("Perguntas Não Respondidas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.list.mockImplementation(async (status) =>
      status === "pending" ? [pending] : status === "review" ? [review] : []
    );
    mocks.approve.mockResolvedValue(undefined);
    mocks.ignore.mockResolvedValue(undefined);
    mocks.restore.mockResolvedValue(undefined);
  });

  it("separa revisão das pendentes e permite aprovação humana", async () => {
    const user = userEvent.setup();
    render(<UnansweredQuestions />);

    expect(await screen.findByText(pending.canonical_question)).toBeInTheDocument();
    expect(screen.queryByText(review.canonical_question)).not.toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledWith("pending");
    expect(mocks.list).toHaveBeenCalledWith("review");
    expect(mocks.list).toHaveBeenCalledWith("ignored");

    await user.click(screen.getByRole("button", { name: "Revisar (1)" }));
    expect(screen.getByText(review.canonical_question)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Responder" })).not.toBeInTheDocument();
    expect(screen.getByText("Revisão necessária: linguagem inadequada.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Enviar para pendentes" }));
    await waitFor(() => expect(mocks.approve).toHaveBeenCalledWith("review-1"));
    expect(screen.getByRole("button", { name: "Revisar (0)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pendentes (2)" }));
    expect(screen.getByText(review.canonical_question)).toBeInTheDocument();
  });

  it("ignora uma pergunta e permite restaurá-la", async () => {
    const user = userEvent.setup();
    render(<UnansweredQuestions />);
    await screen.findByText(pending.canonical_question);

    await user.click(screen.getByRole("button", { name: "Ignorar pergunta" }));
    await user.click(screen.getByRole("button", { name: /^Ignorar$/ }));

    await waitFor(() => expect(mocks.ignore).toHaveBeenCalledWith("pending-1"));
    expect(screen.queryByText(pending.canonical_question)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ignoradas (1)" }));
    expect(screen.getByText(pending.canonical_question)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restaurar" }));
    await waitFor(() => expect(mocks.restore).toHaveBeenCalledWith("pending-1"));
    await user.click(screen.getByRole("button", { name: "Pendentes (1)" }));
    expect(screen.getByText(pending.canonical_question)).toBeInTheDocument();
  });
});

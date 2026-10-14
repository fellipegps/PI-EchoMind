import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("./components/faq-tab", () => ({ FaqTab: () => <div>Conteúdo de FAQs</div> }));
vi.mock("./components/document-tab", () => ({ DocumentTab: () => <div>Conteúdo de documentos</div> }));

import KnowledgeBasePage from "./page";

describe("KnowledgeBasePage", () => {
  it("mantém FAQs inicial e permite percorrer somente FAQs e Documentos por teclado", async () => {
    const user = userEvent.setup();
    render(<KnowledgeBasePage />);

    expect(screen.getByRole("tab", { name: "FAQs" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Documentos" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(2);
    expect(screen.getByRole("tab", { name: "FAQs" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Conteúdo de FAQs")).toBeInTheDocument();
    screen.getByRole("tab", { name: "FAQs" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Documentos" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Conteúdo de documentos")).toBeInTheDocument();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "FAQs" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Gerencie as FAQs e os documentos usados pelo chatbot.")).toBeInTheDocument();
  });
});

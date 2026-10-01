import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("./components/faq-tab", () => ({ FaqTab: () => <div>Conteúdo de FAQs</div> }));
vi.mock("./components/document-tab", () => ({ DocumentTab: () => <div>Conteúdo de documentos</div> }));

import KnowledgeBasePage from "./page";

describe("KnowledgeBasePage", () => {
  it("mantém somente FAQs e Documentos na base de conhecimento", () => {
    render(<KnowledgeBasePage />);

    expect(screen.getByRole("tab", { name: "FAQs" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Documentos" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Eventos" })).not.toBeInTheDocument();
    expect(screen.getByText("Gerencie as FAQs e os documentos usados pelo chatbot.")).toBeInTheDocument();
  });
});

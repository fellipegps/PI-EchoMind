import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import PrivacyPage from "./page";

it("divulga o contato autorizado do projeto e as limitações do filtro", () => {
  render(<PrivacyPage />);
  expect(screen.getByRole("heading", { name: "Contato da equipe Horizon Code" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "fellipe.silva@aluno.unievangelica.edu.br" })).toHaveAttribute("href", expect.stringMatching(/^mailto:fellipe\.silva%40aluno\.unievangelica\.edu\.br\?subject=/));
  expect(screen.getByText(/A mensagem original chega à API/)).toHaveTextContent("O filtro não reconhece todos os dados pessoais");
  expect(screen.getByRole("heading", { name: "Responsabilidades no atendimento" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Contato da equipe Horizon Code" })).toHaveAttribute("id", "contato-equipe");
  expect(screen.getByText(/Este é o contato da equipe do projeto/)).toBeInTheDocument();
});

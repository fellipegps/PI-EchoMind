import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const getInstitution = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ publicPortalApi: { getInstitution } }));
import { InstitutionPrivacy } from "./institution-privacy";

beforeEach(() => vi.resetAllMocks());

it("publica o contato, a finalidade e o prazo da instituição correta", async () => {
  getInstitution.mockResolvedValue({
    company_name: "Instituição Sintética", privacy_controller: "Controlador Sintético",
    privacy_email: "privacidade@example.com", privacy_purpose: "Atendimento ao público.",
    privacy_legal_basis: "Base aprovada", chat_retention_days: 30,
    chat_retention_enabled: true, privacy_ready: true,
  });
  render(<InstitutionPrivacy publicSlug="instituicao-sintetica" />);
  expect(await screen.findByText(/Controlador: Controlador Sintético/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "privacidade@example.com" })).toHaveAttribute("href", expect.stringMatching(/^mailto:privacidade%40example\.com\?subject=/));
  expect(screen.getByText(/Prazo adotado para o histórico: 30 dias/)).toBeInTheDocument();
  expect(getInstitution).toHaveBeenCalledWith("instituicao-sintetica");
});

it("separa o contato da equipe técnica do canal institucional ainda não cadastrado", async () => {
  getInstitution.mockResolvedValue({ company_name: "Instituição Sintética", privacy_ready: false });
  render(<InstitutionPrivacy publicSlug="instituicao" />);
  expect(await screen.findByText(/O chat está indisponível/)).toBeInTheDocument();
  expect(screen.getByText(/O canal de privacidade da instituição ainda não foi cadastrado/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /@/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Contato da equipe técnica Horizon Code" })).toHaveAttribute("href", "/privacidade#contato-equipe");
});

it("informa falha de carregamento sem exibir uma política genérica como cadastrada", async () => {
  getInstitution.mockRejectedValue(new Error("Falha sintética"));
  render(<InstitutionPrivacy publicSlug="instituicao" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar");
  expect(screen.queryByText("Responsável e contato")).not.toBeInTheDocument();
});

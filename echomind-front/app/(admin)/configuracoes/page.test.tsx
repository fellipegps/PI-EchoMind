import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ get: vi.fn(), save: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock("@/lib/api", () => ({ configApi: { get: mocks.get, save: mocks.save } }));
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }));
vi.mock("./public-portal-card", () => ({ PublicPortalCard: ({ publicSlug }: { publicSlug: string }) => <div aria-label="Slug retornado">{publicSlug}</div> }));
import SettingsPage from "./page";

const config = {
  id: "internal-id", public_slug: "instituicao", company_name: "Instituição de teste", description: "Contexto de teste",
  tone_of_voice: "descontraído e jovem", chat_voice_gender: "masculina", website: "https://example.test", phone: "0000",
  address: "Rua fictícia", business_hours: "9h–18h", updated_at: null,
};

describe("Configurações — contrato DS-15", () => {
  beforeEach(() => { vi.resetAllMocks(); mocks.get.mockResolvedValue(config); });

  it("identifica carregamento e associa rótulos aos oito campos/opções carregados", async () => {
    let resolve!: (value: unknown) => void;
    mocks.get.mockReturnValue(new Promise(r => { resolve = r; }));
    render(<SettingsPage />);
    expect(screen.getByRole("status", { name: "Carregando configurações" })).toBeInTheDocument();
    await act(async () => resolve(config));
    for (const [label, value] of [["Nome da Instituição", config.company_name], ["Descrição Base (Contexto)", config.description], ["Website Oficial", config.website], ["Telefone de Contato", config.phone], ["Endereço", config.address], ["Horário de Funcionamento", config.business_hours]]) {
      expect(screen.getByLabelText(label)).toHaveValue(value);
    }
    expect(screen.getByRole("combobox", { name: "Personalidade da IA" })).toHaveTextContent("Descontraído e jovem");
    expect(screen.getByRole("combobox", { name: "Voz do Chatbot" })).toHaveTextContent("Masculino (pt-BR)");
  });

  it("preserva defaults quando a carga falha, sem validação nova nem slug inventado", async () => {
    mocks.get.mockRejectedValue(new Error("Sem configuração"));
    mocks.save.mockResolvedValue(config);
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByLabelText("Nome da Instituição")).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "Personalidade da IA" })).toHaveTextContent("Profissional e cordial");
    expect(screen.getByRole("combobox", { name: "Voz do Chatbot" })).toHaveTextContent("Feminina (pt-BR)");
    expect(screen.getByLabelText("Slug retornado")).toBeEmptyDOMElement();
    await user.click(screen.getByRole("button", { name: "Salvar Alterações" }));
    expect(mocks.save).toHaveBeenCalledWith({ company_name: "", description: "", tone_of_voice: "profissional e cordial", chat_voice_gender: "feminina", website: "", phone: "", address: "", business_hours: "" });
  });

  it("nomeia salvamento pendente e usa o retorno da API como fonte após sucesso", async () => {
    let resolve!: (value: unknown) => void;
    mocks.save.mockReturnValue(new Promise(r => { resolve = r; }));
    const user = userEvent.setup();
    render(<SettingsPage />);
    const input = await screen.findByLabelText("Nome da Instituição");
    await user.clear(input); await user.type(input, "Edição local");
    await user.click(screen.getByRole("button", { name: "Salvar Alterações" }));
    expect(screen.getByRole("button", { name: "Salvando…" })).toBeDisabled();
    expect(mocks.save).toHaveBeenCalledWith({ ...config, company_name: "Edição local" });
    await act(async () => resolve({ ...config, company_name: "Normalizado pelo servidor", public_slug: "slug-da-api" }));
    expect(input).toHaveValue("Normalizado pelo servidor");
    expect(screen.getByLabelText("Slug retornado")).toHaveTextContent("slug-da-api");
    expect(mocks.success).toHaveBeenCalledWith("Configurações atualizadas com sucesso!");
  });

  it("mantém a edição quando salvar falha e libera nova tentativa", async () => {
    mocks.save.mockRejectedValue(new Error("Falha sintética de envio"));
    const user = userEvent.setup();
    render(<SettingsPage />);
    const input = await screen.findByLabelText("Website Oficial");
    await user.clear(input); await user.type(input, "texto sem validação nova");
    await user.click(screen.getByRole("button", { name: "Salvar Alterações" }));
    await waitFor(() => expect(mocks.error).toHaveBeenCalledWith("Falha sintética de envio"));
    expect(input).toHaveValue("texto sem validação nova");
    expect(screen.getByRole("button", { name: "Salvar Alterações" })).toBeEnabled();
  });
});

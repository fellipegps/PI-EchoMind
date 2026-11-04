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

describe("Configurações — contrato DS-15 com simplificação autorizada", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    mocks.get.mockResolvedValue(config);
  });

  it("identifica carregamento, associa os seis campos e remove opções de personalidade/voz", async () => {
    let resolve!: (value: unknown) => void;
    mocks.get.mockReturnValue(new Promise(r => { resolve = r; }));
    render(<SettingsPage />);
    expect(screen.getByRole("status", { name: "Carregando configurações" })).toBeInTheDocument();
    await act(async () => resolve(config));
    for (const [label, value] of [["Nome da Instituição", config.company_name], ["Descrição Base (Contexto)", config.description], ["Website Oficial", config.website], ["Telefone de Contato", config.phone], ["Endereço", config.address], ["Horário de Funcionamento", config.business_hours]]) {
      expect(screen.getByLabelText(label)).toHaveValue(value);
    }
    expect(screen.queryByRole("combobox", { name: "Personalidade da IA" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Voz do Chatbot" })).not.toBeInTheDocument();
    expect(screen.queryByText("Comportamento do agente")).not.toBeInTheDocument();
  });

  it("preserva defaults quando a carga falha, sem validação nova nem slug inventado", async () => {
    mocks.get.mockRejectedValue(new Error("Sem configuração"));
    mocks.save.mockResolvedValue(config);
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByLabelText("Nome da Instituição")).toHaveValue("");
    expect(screen.getByLabelText("Slug retornado")).toBeEmptyDOMElement();
    await user.click(screen.getByRole("button", { name: "Salvar Alterações" }));
    expect(mocks.save).toHaveBeenCalledWith({ company_name: "", description: "", website: "", phone: "", address: "", business_hours: "" });
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
    expect(mocks.save).toHaveBeenCalledWith({ company_name: "Edição local", description: config.description, website: config.website, phone: config.phone, address: config.address, business_hours: config.business_hours });
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

  it("salva o contato e o prazo aprovados sem enviar outros campos da instituição", async () => {
    const privacy = {
      privacy_controller: "Instituição Sintética", privacy_email: "privacidade@example.com",
      privacy_purpose: "Atendimento institucional ao público.", privacy_legal_basis: "Base aprovada pela instituição.",
      chat_retention_days: 30, chat_retention_enabled: true,
    };
    mocks.save.mockResolvedValue({ ...config, ...privacy, privacy_ready: true });
    const user = userEvent.setup();
    render(<SettingsPage />);
    await screen.findByLabelText("Instituição responsável pelos dados");
    await user.type(screen.getByLabelText("Instituição responsável pelos dados"), privacy.privacy_controller);
    await user.clear(screen.getByLabelText("E-mail para pedidos de privacidade"));
    await user.type(screen.getByLabelText("E-mail para pedidos de privacidade"), privacy.privacy_email);
    await user.type(screen.getByLabelText("Finalidade do uso dos dados no chat"), privacy.privacy_purpose);
    await user.type(screen.getByLabelText("Base legal definida pela instituição"), privacy.privacy_legal_basis);
    await user.type(screen.getByLabelText("Prazo do histórico de chat, em dias"), "30");
    await user.click(screen.getByRole("switch", { name: "Ativar limpeza automática do histórico" }));
    await user.click(screen.getByRole("button", { name: "Salvar privacidade" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(privacy));
    expect(await screen.findByText(/Informações de privacidade cadastradas/)).toBeInTheDocument();
  });

  it("mantém o contato e a política vazios até o cadastro da instituição", async () => {
    render(<SettingsPage />);
    expect(await screen.findByLabelText("E-mail para pedidos de privacidade")).toHaveValue("");
    expect(screen.getByLabelText("Base legal definida pela instituição")).toHaveValue("");
    expect(screen.getByLabelText("Prazo do histórico de chat, em dias")).toHaveValue(null);
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it("preserva o contato específico já cadastrado pela instituição", async () => {
    mocks.get.mockResolvedValue({ ...config, privacy_email: "equipe@example.test" });
    render(<SettingsPage />);
    expect(await screen.findByLabelText("E-mail para pedidos de privacidade")).toHaveValue("equipe@example.test");
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it.each(["UniEVANGÉLICA", "Instituição sintética", " unievangelica "])("não cria uma política a partir do nome da instituição: %s", async company => {
    mocks.get.mockResolvedValue({ ...config, company_name: company, privacy_ready: false, chat_retention_enabled: false });
    render(<SettingsPage />);
    expect(await screen.findByLabelText("Instituição responsável pelos dados")).toHaveValue("");
    expect(screen.getByLabelText("E-mail para pedidos de privacidade")).toHaveValue("");
    expect(screen.getByLabelText("Finalidade do uso dos dados no chat")).toHaveValue("");
    expect(screen.getByLabelText("Prazo do histórico de chat, em dias")).toHaveValue(null);
    expect(screen.getByLabelText("Base legal definida pela instituição")).toHaveValue("");
    expect(screen.getByRole("switch", { name: "Ativar limpeza automática do histórico" })).not.toBeChecked();
    expect(screen.getByText(/Conclua os campos e ative a limpeza/)).toBeInTheDocument();
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it("preserva os valores já cadastrados, inclusive outro prazo aprovado", async () => {
    const existing = {
      privacy_controller: "Responsável cadastrado", privacy_email: "equipe@example.test",
      privacy_purpose: "Finalidade já cadastrada", privacy_legal_basis: "Base já cadastrada",
      chat_retention_days: 60, chat_retention_enabled: true, privacy_ready: true,
    };
    mocks.get.mockResolvedValue({ ...config, company_name: "UniEVANGÉLICA", ...existing });
    render(<SettingsPage />);
    expect(await screen.findByLabelText("Instituição responsável pelos dados")).toHaveValue(existing.privacy_controller);
    expect(screen.getByLabelText("Finalidade do uso dos dados no chat")).toHaveValue(existing.privacy_purpose);
    expect(screen.getByLabelText("Prazo do histórico de chat, em dias")).toHaveValue(60);
    expect(screen.getByLabelText("Base legal definida pela instituição")).toHaveValue(existing.privacy_legal_basis);
    expect(screen.getByLabelText("E-mail para pedidos de privacidade")).toHaveValue(existing.privacy_email);
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it("salva o cadastro incompleto sem base legal, sem ativar limpeza nem liberar atendimento", async () => {
    const draft = {
      privacy_controller: "Instituição sintética", privacy_email: "privacy@example.test",
      privacy_purpose: "Atendimento de dúvidas gerais.", chat_retention_days: 30,
      privacy_legal_basis: null, chat_retention_enabled: false,
    };
    mocks.get.mockResolvedValue({ ...config, ...draft, privacy_ready: false });
    mocks.save.mockResolvedValue({ ...config, ...draft, privacy_ready: false });
    const user = userEvent.setup();
    render(<SettingsPage />);
    const basis = await screen.findByLabelText("Base legal definida pela instituição");
    expect(basis).not.toBeRequired();
    await user.click(screen.getByRole("button", { name: "Salvar privacidade" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(draft));
    expect(screen.getByText(/Conclua os campos e ative a limpeza/)).toBeInTheDocument();
    expect(basis).toHaveValue("");
    await user.click(screen.getByRole("switch", { name: "Ativar limpeza automática do histórico" }));
    expect(basis).toBeRequired();
    await user.click(screen.getByRole("button", { name: "Salvar privacidade" }));
    expect(mocks.save).toHaveBeenCalledTimes(1);
  });

  it("não atribui a UniEVANGÉLICA ou o prazo de 30 dias a outra instituição", async () => {
    render(<SettingsPage />);
    expect(await screen.findByLabelText("Instituição responsável pelos dados")).toHaveValue("");
    expect(screen.getByLabelText("Finalidade do uso dos dados no chat")).toHaveValue("");
    expect(screen.getByLabelText("Prazo do histórico de chat, em dias")).toHaveValue(null);
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it("salvar os dados gerais preserva a edição de privacidade sem publicá-la", async () => {
    mocks.get.mockResolvedValue({ ...config, privacy_purpose: "Finalidade cadastrada.", chat_retention_days: 30, privacy_ready: false, chat_retention_enabled: false });
    mocks.save.mockResolvedValue({ ...config, company_name: "UniEVANGÉLICA", privacy_purpose: null, chat_retention_days: null, privacy_ready: false, chat_retention_enabled: false });
    const user = userEvent.setup();
    render(<SettingsPage />);
    const purpose = await screen.findByLabelText("Finalidade do uso dos dados no chat");
    await user.clear(purpose); await user.type(purpose, "Finalidade em revisão pela equipe.");
    await user.click(screen.getByRole("button", { name: "Salvar Alterações" }));
    await waitFor(() => expect(mocks.success).toHaveBeenCalledWith("Configurações atualizadas com sucesso!"));
    expect(purpose).toHaveValue("Finalidade em revisão pela equipe.");
    expect(screen.getByLabelText("Prazo do histórico de chat, em dias")).toHaveValue(30);
    expect(mocks.save).toHaveBeenCalledWith(expect.not.objectContaining({ privacy_purpose: expect.anything() }));
    expect(mocks.save).toHaveBeenCalledTimes(1);
  });

  it("salvar os dados gerais não repõe os campos de privacidade apagados na edição", async () => {
    mocks.get.mockResolvedValue({ ...config, privacy_purpose: "Finalidade cadastrada.", chat_retention_days: 30, privacy_ready: false });
    mocks.save.mockResolvedValue({ ...config, company_name: "UniEVANGÉLICA", privacy_ready: false });
    const user = userEvent.setup();
    render(<SettingsPage />);
    const purpose = await screen.findByLabelText("Finalidade do uso dos dados no chat");
    await user.clear(purpose);
    await user.clear(screen.getByLabelText("Prazo do histórico de chat, em dias"));
    await user.click(screen.getByRole("button", { name: "Salvar Alterações" }));
    await waitFor(() => expect(mocks.success).toHaveBeenCalled());
    expect(purpose).toHaveValue("");
    expect(screen.getByLabelText("Prazo do histórico de chat, em dias")).toHaveValue(null);
  });
});

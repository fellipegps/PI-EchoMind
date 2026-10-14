import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  toDataURL: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("qrcode", () => ({
  default: { toDataURL: mocks.toDataURL },
}));

vi.mock("sonner", () => ({
  toast: { success: mocks.toastSuccess, error: mocks.toastError },
}));

import { PublicPortalCard } from "./public-portal-card";

describe("PublicPortalCard", () => {
  beforeEach(() => {
    mocks.toDataURL.mockReset();
    mocks.toastSuccess.mockReset();
    mocks.toastError.mockReset();
    mocks.toDataURL.mockResolvedValue("data:image/png;base64,qr-local");
  });

  it("gera QR local e oferece copiar, abrir e baixar a URL por slug", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText");
    render(<PublicPortalCard publicSlug="unievangelica-anapolis" />);

    const expectedUrl = `${window.location.origin}/p/unievangelica-anapolis`;
    expect(await screen.findByAltText("QR Code do portal público")).toBeInTheDocument();
    expect(screen.getByLabelText("URL do portal público")).toHaveValue(expectedUrl);
    expect(mocks.toDataURL).toHaveBeenCalledWith(
      expectedUrl,
      expect.objectContaining({ width: 256 })
    );

    await user.click(screen.getByRole("button", { name: "Copiar link" }));
    expect(writeText).toHaveBeenCalledWith(expectedUrl);
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Link do portal copiado!");

    const download = screen.getByRole("link", { name: "Baixar QR" });
    expect(download).toHaveAttribute("href", "data:image/png;base64,qr-local");
    expect(download).toHaveAttribute("download", "portal-unievangelica-anapolis.png");
  });

  it("trata falha de geração sem expor detalhes internos", async () => {
    mocks.toDataURL.mockRejectedValue(new Error("segredo interno"));

    render(<PublicPortalCard publicSlug="instituicao-valida" />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Não foi possível gerar o QR Code agora."
      );
    });
    expect(screen.getByRole("alert")).not.toHaveTextContent("segredo interno");
  });

  it("apara e codifica slug, preserva parâmetros funcionais e protege a nova janela", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    const user = userEvent.setup();
    render(<PublicPortalCard publicSlug="  instituição / centro  " />);
    await screen.findByAltText("QR Code do portal público");
    const url = `${window.location.origin}/p/${encodeURIComponent("instituição / centro")}`;
    expect(screen.getByLabelText("URL do portal público")).toHaveValue(url);
    expect(screen.getByLabelText("URL do portal público")).toHaveAttribute("readonly");
    expect(mocks.toDataURL).toHaveBeenCalledWith(url, {
      errorCorrectionLevel: "M", margin: 2, width: 256, color: { dark: "#172554", light: "#ffffff" },
    });
    await user.click(screen.getByRole("button", { name: "Abrir portal" }));
    expect(open).toHaveBeenCalledWith(url, "_blank", "noopener,noreferrer");
    open.mockRestore();
  });

  it("não inventa URL ou QR para slug vazio, inclusive somente espaços", () => {
    render(<PublicPortalCard publicSlug="   " />);
    expect(mocks.toDataURL).not.toHaveBeenCalled();
    expect(screen.getByLabelText("URL do portal público")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Copiar link" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Abrir portal" })).toBeDisabled();
    expect(screen.queryByRole("link", { name: "Baixar QR" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Salve a configuração institucional");
  });

  it("ignora o QR atrasado de um slug anterior e limpa conteúdo ao remover slug", async () => {
    let resolveOld!: (value: string) => void;
    let resolveNew!: (value: string) => void;
    mocks.toDataURL.mockImplementationOnce(() => new Promise(r => { resolveOld = r; }))
      .mockImplementationOnce(() => new Promise(r => { resolveNew = r; }));
    const { rerender } = render(<PublicPortalCard publicSlug="anterior" />);
    expect(screen.getByRole("status")).toHaveTextContent("Gerando QR Code");
    rerender(<PublicPortalCard publicSlug="atual" />);
    await act(async () => resolveOld("data:image/png;base64,old"));
    expect(screen.queryByAltText("QR Code do portal público")).not.toBeInTheDocument();
    await act(async () => resolveNew("data:image/png;base64,new"));
    expect(screen.getByAltText("QR Code do portal público")).toHaveAttribute("src", "data:image/png;base64,new");
    expect(screen.getByLabelText("URL do portal público")).toHaveValue(`${window.location.origin}/p/atual`);
    rerender(<PublicPortalCard publicSlug="" />);
    expect(screen.getByLabelText("URL do portal público")).toHaveValue("");
    expect(screen.queryByAltText("QR Code do portal público")).not.toBeInTheDocument();
  });

  it("comunica falha de clipboard sem detalhes internos e mantém link disponível", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValueOnce(new Error("SEGREDO_INTERNO"));
    render(<PublicPortalCard publicSlug="instituicao" />);
    await screen.findByAltText("QR Code do portal público");
    await user.click(screen.getByRole("button", { name: "Copiar link" }));
    expect(mocks.toastError).toHaveBeenCalledWith("Não foi possível copiar o link.");
    expect(screen.getByRole("button", { name: "Abrir portal" })).toBeEnabled();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
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
});

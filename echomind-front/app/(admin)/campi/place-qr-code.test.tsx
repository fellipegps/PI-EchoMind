import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
const toDataURL = vi.hoisted(() => vi.fn());
vi.mock("qrcode", () => ({ default: { toDataURL } }));
vi.mock("@/lib/api", () => ({ tokenStore: { get: vi.fn(), clear: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
import { PlaceQrCode } from "./place-qr-code";
import { toast } from "sonner";
const props = { publicSlug: "universidade", placeType: "building" as const, publicCode: "stable-bloco", placeName: "Bloco A" };
beforeEach(() => {
  vi.clearAllMocks();
  toDataURL.mockResolvedValue("data:image/png;base64,qr");
});

describe("PlaceQrCode", () => {
  it("gera QR e download para a mesma ficha pública do mapa", async () => {
    render(<PlaceQrCode {...props} />);
    const url = window.location.origin + "/p/universidade/locais/building/stable-bloco";
    expect(await screen.findByRole("img", { name: "QR Code de Bloco A" })).toBeInTheDocument();
    expect(toDataURL).toHaveBeenCalledWith(url, expect.objectContaining({ width: 512, color: { dark: "#000000", light: "#ffffff" } }));
    expect(screen.getByLabelText("Link público do local")).toHaveValue(url);
    expect(screen.getByRole("link", { name: "Abrir ficha" })).toHaveAttribute("href", url);
    expect(screen.getByRole("link", { name: "Baixar QR Code" })).toHaveAttribute("download", "local-stable-bloco.png");
  });

  it("mudar o nome preserva o endereço codificado", async () => {
    const { rerender } = render(<PlaceQrCode {...props} />);
    await screen.findByRole("img", { name: "QR Code de Bloco A" });
    rerender(<PlaceQrCode {...props} placeName="Bloco reformado" />);
    expect(screen.getByRole("img", { name: "QR Code de Bloco reformado" })).toBeInTheDocument();
    expect(toDataURL).toHaveBeenCalledTimes(1);
  });

  it("imprime apenas após ação e carrega o QR antes de abrir o diálogo", async () => {
    const user = userEvent.setup();
    const doc = document.implementation.createHTMLDocument();
    const print = vi.fn();
    const focus = vi.fn();
    const target = { document: doc, print, focus, opener: window } as unknown as Window;
    const open = vi.spyOn(window, "open").mockReturnValue(target);
    render(<PlaceQrCode {...props} placeName="<script>nome</script>" />);
    await screen.findByRole("img", { name: "QR Code de <script>nome</script>" });
    expect(open).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Imprimir QR Code" }));
    expect(doc.querySelector("h1")?.textContent).toBe("<script>nome</script>");
    expect(doc.querySelector("script")).toBeNull();
    expect(print).not.toHaveBeenCalled();
    doc.querySelector("img")!.dispatchEvent(new Event("load"));
    expect(print).toHaveBeenCalledTimes(1);
    expect(target.opener).toBeNull();
    open.mockRestore();
  });

  it("comunica bloqueio da janela e falha da geração", async () => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    const { unmount } = render(<PlaceQrCode {...props} />);
    await screen.findByRole("img", { name: "QR Code de Bloco A" });
    await user.click(screen.getByRole("button", { name: "Imprimir QR Code" }));
    expect(toast.error).toHaveBeenCalledWith("Permita a abertura da janela para imprimir o QR Code.");
    unmount();
    toDataURL.mockRejectedValueOnce(new Error("qr"));
    render(<PlaceQrCode {...props} />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Não foi possível gerar o QR Code"));
    expect(screen.getByRole("button", { name: "Imprimir QR Code" })).toBeDisabled();
    open.mockRestore();
  });
});

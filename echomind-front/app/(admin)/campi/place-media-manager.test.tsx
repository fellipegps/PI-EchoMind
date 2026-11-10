import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const api = vi.hoisted(() => ({ upload: vi.fn(), delete: vi.fn(), content: vi.fn() }));
vi.mock("@/lib/geocampus-api", () => ({ geoCampusApi: { photos: api } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
import { PlaceMediaManager } from "./place-media-manager";
import { toast } from "sonner";
const props = { campusId: "campus", placeType: "building" as const, placeId: "bloco", placeName: "Bloco A", photos: [], onChanged: vi.fn().mockResolvedValue(undefined) };
const photo = { id: "photo-1", caption: "Fachada", sort_order: 0, url: "/foto" };
const createUrl = vi.fn(() => "blob:photo-preview");
const revokeUrl = vi.fn();
beforeEach(() => {
  vi.clearAllMocks();
  api.upload.mockReset();
  api.delete.mockResolvedValue(undefined);
  api.content.mockResolvedValue(new Blob(["photo"], { type: "image/jpeg" }));
  props.onChanged.mockReset().mockResolvedValue(undefined);
  vi.stubGlobal("URL", class extends URL { static createObjectURL = createUrl; static revokeObjectURL = revokeUrl; });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("PlaceMediaManager", () => {
  it("envia várias fotos sequencialmente com legenda no local correto", async () => {
    const user = userEvent.setup();
    api.upload.mockResolvedValue(photo);
    render(<PlaceMediaManager {...props} />);
    const first = new File(["first"], "entrada.jpg", { type: "image/jpeg" });
    const second = new File(["second"], "fachada.webp", { type: "image/webp" });
    await user.upload(screen.getByLabelText("Adicionar fotos de referência"), [first, second]);
    await user.type(screen.getByLabelText("Descrição das fotos selecionadas (opcional)"), "Entrada principal");
    await user.click(screen.getByRole("button", { name: "Enviar fotos" }));
    await waitFor(() => expect(props.onChanged).toHaveBeenCalledTimes(1));
    expect(api.upload.mock.calls).toEqual([
      ["campus", "building", "bloco", first, "Entrada principal"],
      ["campus", "building", "bloco", second, "Entrada principal"],
    ]);
    expect(screen.getByRole("button", { name: "Enviar fotos" })).toBeDisabled();
  });

  it("preserva fotos já aceitas e a repetição envia somente as restantes", async () => {
    const user = userEvent.setup();
    api.upload.mockResolvedValueOnce(photo).mockRejectedValueOnce(new Error("Falha no segundo arquivo")).mockResolvedValueOnce(photo);
    render(<PlaceMediaManager {...props} />);
    const first = new File(["a"], "a.png", { type: "image/png" });
    const second = new File(["b"], "b.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("Adicionar fotos de referência"), [first, second]);
    await user.click(screen.getByRole("button", { name: "Enviar fotos" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Falha no segundo arquivo 1 foto(s) já foram salvas."));
    await user.click(screen.getByRole("button", { name: "Enviar fotos" }));
    await waitFor(() => expect(api.upload).toHaveBeenCalledTimes(3));
    expect(api.upload.mock.calls[2][3]).toBe(second);
  });

  it("libera o envio se a atualização da lista falhar depois de salvar", async () => {
    const user = userEvent.setup();
    props.onChanged.mockRejectedValueOnce(new Error("refresh"));
    api.upload.mockResolvedValue(photo);
    render(<PlaceMediaManager {...props} />);
    const file = new File(["a"], "a.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("Adicionar fotos de referência"), file);
    await user.click(screen.getByRole("button", { name: "Enviar fotos" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("As fotos foram salvas, mas a lista não pôde ser atualizada. Abra este local novamente."));
    await user.upload(screen.getByLabelText("Adicionar fotos de referência"), file);
    expect(screen.getByRole("button", { name: "Enviar fotos" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Enviar fotos" }));
    await waitFor(() => expect(api.upload).toHaveBeenCalledTimes(2));
  });

  it("recusa arquivo maior que 5 MiB antes do upload", async () => {
    render(<PlaceMediaManager {...props} />);
    const file = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "grande.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Adicionar fotos de referência"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar fotos" }));
    expect(api.upload).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith("Escolha fotos JPEG, PNG ou WebP de até 5 MiB cada.");
  });

  it("carrega a foto autenticada e libera o object URL ao desmontar", async () => {
    const { unmount } = render(<PlaceMediaManager {...props} photos={[photo]} />);
    expect(await screen.findByRole("img", { name: "Fachada" })).toHaveAttribute("src", "blob:photo-preview");
    expect(api.content).toHaveBeenCalledWith("campus", "building", "bloco", "photo-1");
    unmount();
    expect(revokeUrl).toHaveBeenCalledWith("blob:photo-preview");
  });

  it("descarta preview recebido depois que o local foi fechado", async () => {
    let resolve!: (value: Blob) => void;
    api.content.mockReturnValueOnce(new Promise<Blob>((done) => { resolve = done; }));
    const { unmount } = render(<PlaceMediaManager {...props} photos={[photo]} />);
    unmount();
    await act(async () => resolve(new Blob(["photo"])));
    expect(createUrl).not.toHaveBeenCalled();
  });

  it("remove foto somente do local indicado e atualiza a listagem", async () => {
    const user = userEvent.setup();
    render(<PlaceMediaManager {...props} photos={[photo]} />);
    await user.click(screen.getByRole("button", { name: "Remover foto 1 de Bloco A" }));
    await waitFor(() => expect(props.onChanged).toHaveBeenCalledTimes(1));
    expect(api.delete).toHaveBeenCalledWith("campus", "building", "bloco", "photo-1");
  });
});

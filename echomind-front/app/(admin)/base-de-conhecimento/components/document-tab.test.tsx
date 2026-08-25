import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const documentApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  documentApi: documentApiMock,
}));

import type { DocumentStatus, KnowledgeDocument } from "@/lib/api";

import { DocumentTab } from "./document-tab";

const DOCX_MIME_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function makeDocument(
  status: DocumentStatus,
  id = `document-${status}`,
  overrides: Partial<KnowledgeDocument> = {}
): KnowledgeDocument {
  return {
    id,
    filename: `${id}.pdf`,
    mime_type: "application/pdf",
    size_bytes: 2048,
    sha256: "a".repeat(64),
    status,
    chunk_count: status === "ready" ? 4 : 0,
    document_type: null,
    document_number: null,
    department: null,
    published_at: null,
    valid_until: null,
    error_message: null,
    created_at: "2026-08-24T10:00:00Z",
    updated_at: "2026-08-24T10:01:00Z",
    processed_at: status === "ready" || status === "error" ? "2026-08-24T10:01:00Z" : null,
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}

async function renderLoaded(documents: KnowledgeDocument[] = []) {
  documentApiMock.list.mockResolvedValueOnce({ documents, total: documents.length });
  render(<DocumentTab />);
  await screen.findByText(documents.length ? documents[0].filename : "Nenhum documento enviado.");
}

describe("DocumentTab", () => {
  beforeEach(() => {
    vi.useRealTimers();
    documentApiMock.list.mockReset();
    documentApiMock.upload.mockReset();
    documentApiMock.delete.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("mostra loading inicial e lista vazia após carregar", async () => {
    const listing = deferred<{ documents: KnowledgeDocument[]; total: number }>();
    documentApiMock.list.mockReturnValueOnce(listing.promise);

    render(<DocumentTab />);

    expect(screen.getByRole("status")).toHaveTextContent("Carregando documentos...");

    listing.resolve({ documents: [], total: 0 });

    expect(await screen.findByText("Nenhum documento enviado.")).toBeInTheDocument();
    expect(screen.queryByText("manual-do-aluno.pdf")).not.toBeInTheDocument();
  });

  it("mostra erro seguro de listagem e permite tentar novamente", async () => {
    const user = userEvent.setup();
    const ready = makeDocument("ready", "document-retry");
    documentApiMock.list
      .mockRejectedValueOnce(new Error("detalhe interno"))
      .mockResolvedValueOnce({ documents: [ready], total: 1 });

    render(<DocumentTab />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar os documentos."
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("detalhe interno");

    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    expect(await screen.findByText(ready.filename)).toBeInTheDocument();
    expect(documentApiMock.list).toHaveBeenCalledTimes(2);
  });

  it("aceita seleção e drag-and-drop de PDF, TXT e DOCX, um arquivo por vez", async () => {
    const user = userEvent.setup();
    await renderLoaded();
    const input = screen.getByLabelText("Selecionar documento");
    const dropzone = screen.getByTestId("document-dropzone");

    const pdf = new File(["pdf"], "manual.pdf", { type: "application/pdf" });
    await user.upload(input, pdf);
    expect(screen.getByRole("form", { name: "Metadados do documento" })).toHaveTextContent(
      "manual.pdf"
    );

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    const txt = new File(["texto"], "norma.txt", { type: "text/plain" });
    fireEvent.drop(dropzone, { dataTransfer: { files: [txt] } });
    expect(screen.getByRole("form", { name: "Metadados do documento" })).toHaveTextContent(
      "norma.txt"
    );

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    const docx = new File(["docx"], "regulamento.docx", { type: DOCX_MIME_TYPE });
    await user.upload(input, docx);
    expect(screen.getByRole("form", { name: "Metadados do documento" })).toHaveTextContent(
      "regulamento.docx"
    );
    expect(input).toHaveAttribute("accept", expect.stringContaining(".txt"));
    expect(input).not.toHaveAttribute("multiple");
  });

  it("rejeita formato, tamanho e seleção múltipla sem chamar upload", async () => {
    await renderLoaded();
    const input = screen.getByLabelText("Selecionar documento");
    const dropzone = screen.getByTestId("document-dropzone");

    const invalid = new File(["executável"], "programa.exe", {
      type: "application/octet-stream",
    });
    fireEvent.change(input, { target: { files: [invalid] } });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Selecione um arquivo PDF, TXT ou DOCX válido."
    );

    const oversized = new File(["pdf"], "grande.pdf", { type: "application/pdf" });
    Object.defineProperty(oversized, "size", { value: 10 * 1024 * 1024 + 1 });
    fireEvent.change(input, { target: { files: [oversized] } });
    expect(screen.getByRole("alert")).toHaveTextContent("O arquivo deve ter no máximo 10 MB.");

    const first = new File(["a"], "a.txt", { type: "text/plain" });
    const second = new File(["b"], "b.txt", { type: "text/plain" });
    fireEvent.drop(dropzone, { dataTransfer: { files: [first, second] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Envie apenas um arquivo por vez.");
    expect(documentApiMock.upload).not.toHaveBeenCalled();
  });

  it("envia metadata opcional e adiciona imediatamente o retorno pending do upload", async () => {
    const user = userEvent.setup();
    const uploaded = makeDocument("pending", "document-upload", {
      filename: "regulamento.pdf",
      document_type: "regulamento",
      document_number: "42/2026",
      department: "Acadêmico",
      published_at: "2026-08-24",
      valid_until: "2027-08-24",
    });
    documentApiMock.upload.mockResolvedValueOnce(uploaded);
    await renderLoaded();

    const file = new File(["pdf"], "regulamento.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Selecionar documento"), file);
    await user.type(screen.getByLabelText("Tipo do documento"), "  regulamento  ");
    await user.type(screen.getByLabelText("Número do documento"), "42/2026");
    await user.type(screen.getByLabelText("Departamento"), "Acadêmico");
    fireEvent.change(screen.getByLabelText("Data de publicação"), {
      target: { value: "2026-08-24" },
    });
    fireEvent.change(screen.getByLabelText("Válido até"), {
      target: { value: "2027-08-24" },
    });

    await user.click(screen.getByRole("button", { name: "Enviar documento" }));

    await waitFor(() => {
      expect(documentApiMock.upload).toHaveBeenCalledWith(file, {
        document_type: "regulamento",
        document_number: "42/2026",
        department: "Acadêmico",
        published_at: "2026-08-24",
        valid_until: "2027-08-24",
      });
    });
    expect(await screen.findByText("Pendente")).toBeInTheDocument();
    expect(screen.getByText(uploaded.filename)).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Metadados do documento" })).not.toBeInTheDocument();
  });

  it("mostra todos os badges, chunk_count e bloqueia exclusão de itens ativos", async () => {
    const documents = [
      makeDocument("pending"),
      makeDocument("processing"),
      makeDocument("ready", "document-ready", { chunk_count: 7 }),
      makeDocument("error"),
    ];
    await renderLoaded(documents);

    const expectations: Array<[KnowledgeDocument, string]> = [
      [documents[0], "Pendente"],
      [documents[1], "Processando"],
      [documents[2], "Pronto"],
      [documents[3], "Erro"],
    ];

    for (const [document, statusLabel] of expectations) {
      const row = screen.getByText(document.filename).closest("tr");
      expect(row).not.toBeNull();
      expect(within(row!).getByText(statusLabel)).toBeInTheDocument();
      expect(within(row!).getByText(String(document.chunk_count))).toBeInTheDocument();
    }

    expect(screen.getByRole("button", { name: `Excluir ${documents[0].filename}` })).toBeDisabled();
    expect(screen.getByRole("button", { name: `Excluir ${documents[1].filename}` })).toBeDisabled();
    expect(screen.getByRole("button", { name: `Excluir ${documents[2].filename}` })).toBeEnabled();
    expect(screen.getByRole("button", { name: `Excluir ${documents[3].filename}` })).toBeEnabled();
  });

  it("mantém polling a cada dois segundos e para quando o documento fica ready", async () => {
    vi.useFakeTimers();
    const pending = makeDocument("pending", "document-poll");
    const processing = makeDocument("processing", "document-poll");
    const ready = makeDocument("ready", "document-poll", { chunk_count: 5 });
    documentApiMock.list
      .mockResolvedValueOnce({ documents: [pending], total: 1 })
      .mockResolvedValueOnce({ documents: [processing], total: 1 })
      .mockResolvedValueOnce({ documents: [ready], total: 1 });

    render(<DocumentTab />);
    await act(async () => Promise.resolve());

    expect(screen.getByText("Pendente")).toBeInTheDocument();
    expect(vi.getTimerCount()).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText("Processando")).toBeInTheDocument();
    expect(documentApiMock.list).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText("Pronto")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(vi.getTimerCount()).toBe(0);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(documentApiMock.list).toHaveBeenCalledTimes(3);
  });

  it("limpa o timer de polling ao desmontar", async () => {
    vi.useFakeTimers();
    const pending = makeDocument("pending", "document-unmount");
    documentApiMock.list.mockResolvedValueOnce({ documents: [pending], total: 1 });

    const view = render(<DocumentTab />);
    await act(async () => Promise.resolve());

    expect(vi.getTimerCount()).toBe(1);
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("remove somente após DELETE bem-sucedido e preserva o item quando falha", async () => {
    const user = userEvent.setup();
    const successDocument = makeDocument("ready", "document-delete-success");
    const failureDocument = makeDocument("error", "document-delete-failure");
    const deletion = deferred<void>();
    documentApiMock.delete
      .mockReturnValueOnce(deletion.promise)
      .mockRejectedValueOnce(new Error("segredo interno"));
    await renderLoaded([successDocument, failureDocument]);

    await user.click(
      screen.getByRole("button", { name: `Excluir ${successDocument.filename}` })
    );
    expect(screen.getByText(successDocument.filename)).toBeInTheDocument();

    deletion.resolve();
    await waitFor(() => {
      expect(screen.queryByText(successDocument.filename)).not.toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: `Excluir ${failureDocument.filename}` })
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível excluir o documento."
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("segredo interno");
    expect(screen.getByText(failureDocument.filename)).toBeInTheDocument();
    expect(documentApiMock.delete).toHaveBeenNthCalledWith(1, successDocument.id);
    expect(documentApiMock.delete).toHaveBeenNthCalledWith(2, failureDocument.id);
  });
});

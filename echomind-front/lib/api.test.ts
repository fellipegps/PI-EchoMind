import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./supabase", () => ({
  supabase: {
    auth: {},
  },
}));

import {
  documentApi,
  type DocumentListResponse,
  type DocumentUploadMetadata,
  type KnowledgeDocument,
  tokenStore,
} from "./api";

const API_URL = "http://localhost:8000";

const document: KnowledgeDocument = {
  id: "document-1",
  filename: "regulamento.pdf",
  mime_type: "application/pdf",
  size_bytes: 2048,
  sha256: "a".repeat(64),
  status: "ready",
  chunk_count: 3,
  document_type: "regulamento",
  document_number: "42/2026",
  department: null,
  published_at: "2026-08-24",
  valid_until: null,
  error_message: null,
  created_at: "2026-08-24T10:00:00Z",
  updated_at: "2026-08-24T10:01:00Z",
  processed_at: "2026-08-24T10:01:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestHeaders(call: unknown[]): Headers {
  const init = call[1] as RequestInit;
  return new Headers(init.headers);
}

describe("documentApi", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.restoreAllMocks();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    localStorage.clear();
    window.history.replaceState({}, "", "/");
    tokenStore.set("token-do-admin");
  });

  it("lista, consulta e exclui documentos com método, URL e autorização corretos", async () => {
    const listing: DocumentListResponse = { documents: [document], total: 1 };
    fetchMock
      .mockResolvedValueOnce(jsonResponse(listing))
      .mockResolvedValueOnce(jsonResponse(document))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(documentApi.list()).resolves.toEqual(listing);
    await expect(documentApi.get("document-1")).resolves.toEqual(document);
    await expect(documentApi.delete("document-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_URL}/documents`,
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_URL}/documents/document-1`,
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      `${API_URL}/documents/document-1`,
      expect.objectContaining({ method: "DELETE" })
    );

    for (const call of fetchMock.mock.calls) {
      expect(requestHeaders(call).get("Authorization")).toBe("Bearer token-do-admin");
    }
  });

  it("envia arquivo e metadata permitida em FormData sem definir Content-Type", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(document, 202));
    const file = new File(["conteúdo sintético"], "regulamento.pdf", {
      type: "application/pdf",
    });
    const metadata = {
      document_type: "regulamento",
      document_number: "42/2026",
      department: "Acadêmico",
      published_at: "2026-08-24",
      valid_until: "2027-08-24",
      tenant_id: "tenant-indevido",
    } as DocumentUploadMetadata & { tenant_id: string };

    await expect(documentApi.upload(file, metadata)).resolves.toEqual(document);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    const body = init?.body;

    expect(url).toBe(`${API_URL}/documents/upload`);
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer token-do-admin");
    expect(headers.has("Content-Type")).toBe(false);
    expect(body).toBeInstanceOf(FormData);

    const formData = body as FormData;
    expect(formData.get("file")).toBe(file);
    expect(formData.get("document_type")).toBe("regulamento");
    expect(formData.get("document_number")).toBe("42/2026");
    expect(formData.get("department")).toBe("Acadêmico");
    expect(formData.get("published_at")).toBe("2026-08-24");
    expect(formData.get("valid_until")).toBe("2027-08-24");
    expect(formData.has("tenant_id")).toBe(false);
  });

  it("envia somente o arquivo quando metadata não é informada", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(document, 202));
    const file = new File(["texto"], "norma.txt", { type: "text/plain" });

    await documentApi.upload(file);

    const formData = fetchMock.mock.calls[0][1]?.body as FormData;
    expect(Array.from(formData.keys())).toEqual(["file"]);
  });

  it("preserva o tratamento existente de 401", async () => {
    window.history.replaceState({}, "", "/login");
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "token inválido" }, 401));

    await expect(documentApi.list()).rejects.toThrow(
      "Sessão expirada. Faça login novamente."
    );
    expect(tokenStore.get()).toBeNull();
    expect(window.location.pathname).toBe("/login");
  });

  it.each([
    [422, "Não foi possível concluir a solicitação."],
    [500, "O servidor não conseguiu concluir a solicitação."],
  ])("converte erro HTTP %i em mensagem segura", async (status, expectedMessage) => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "stack trace e segredo interno" }, status)
    );

    const error = await documentApi.list().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toBe(expectedMessage);
    expect((error as Error).message).not.toContain("stack trace");
  });
});

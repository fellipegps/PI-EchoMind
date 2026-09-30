import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./supabase", () => ({ supabase: { auth: {} } }));

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("frontend publicado antes do backend", () => {
  it("nao tenta chamar localhost quando a URL da API esta ausente", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.resetModules();

    const { publicPortalApi, streamPublicChat } = await import("./api");

    await expect(publicPortalApi.getInstitution("campus")).rejects.toThrow(
      "O servidor do EchoMind ainda não está disponível."
    );

    const onError = vi.fn();
    await streamPublicChat("Olá", "campus", vi.fn(), vi.fn(), onError);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "O servidor do EchoMind ainda não está disponível.",
      })
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

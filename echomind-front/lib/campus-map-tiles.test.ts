import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

beforeEach(() => vi.resetModules());
afterEach(() => vi.unstubAllEnvs());

describe("Imagens do mapa do campus", () => {
  it("envia somente a origem do site ao provedor padrão", async () => {
    vi.stubEnv("NEXT_PUBLIC_MAP_TILE_URL", "");

    const { CAMPUS_MAP_TILE_URL, CAMPUS_MAP_TILE_OPTIONS } = await import("./campus-map-tiles");

    expect(CAMPUS_MAP_TILE_URL).toBe("https://tile.openstreetmap.org/{z}/{x}/{y}.png");
    expect(CAMPUS_MAP_TILE_OPTIONS.referrerPolicy).toBe("strict-origin");
  });

  it("herda a política de privacidade da página para outros provedores", async () => {
    const url = "https://maps.example.org/{z}/{x}/{y}.png";
    vi.stubEnv("NEXT_PUBLIC_MAP_TILE_URL", url);

    const { CAMPUS_MAP_TILE_URL, CAMPUS_MAP_TILE_OPTIONS } = await import("./campus-map-tiles");

    expect(CAMPUS_MAP_TILE_URL).toBe(url);
    expect(CAMPUS_MAP_TILE_OPTIONS.referrerPolicy).toBeUndefined();
  });
});

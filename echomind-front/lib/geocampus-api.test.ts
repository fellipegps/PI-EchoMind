import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api", () => ({ tokenStore: { get: () => "admin-token", clear: vi.fn() } }));

import { geoCampusApi } from "./geocampus-api";

describe("geoCampusApi", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("envia autenticação no cadastro do campus e mantém o tenant fora do payload", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "campus-1" }),
    } as Response);

    await geoCampusApi.campuses.create({
      name: "Campus Central",
      description: null,
      center_lat: -16.328,
      center_lng: -48.953,
      zoom: 17,
      active: true,
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/campuses");
    expect(new Headers((init as RequestInit).headers).get("Authorization")).toBe("Bearer admin-token");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      name: "Campus Central",
      description: null,
      center_lat: -16.328,
      center_lng: -48.953,
      zoom: 17,
      active: true,
    });
  });

  it("consulta o mapa público com slug codificado e sem token administrativo", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ campuses: [], buildings: [], spaces: [], nodes: [], edges: [] }),
    } as Response);

    await geoCampusApi.publicMap("instituição central");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/public/institui%C3%A7%C3%A3o%20central/geo-campus");
    expect(new Headers((init as RequestInit).headers).has("Authorization")).toBe(false);
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api", () => ({ tokenStore: { get: () => "admin-token", clear: vi.fn() } }));

import { campusPhotoUrl, geoCampusApi, publicPlaceHref } from "./geocampus-api";

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
      json: async () => ({ campuses: [], buildings: [], spaces: [], landmarks: [] }),
    } as Response);

    await geoCampusApi.publicMap("instituição central");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/public/institui%C3%A7%C3%A3o%20central/geo-campus");
    expect(new Headers((init as RequestInit).headers).has("Authorization")).toBe(false);
  });

  it("consulta a mesma ficha pública usada no link do QR sem credencial administrativa", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({}) } as Response);

    await geoCampusApi.publicPlace("instituição central", "space", "codigo-estavel");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/public/institui%C3%A7%C3%A3o%20central/places/space/codigo-estavel");
    expect(new Headers((init as RequestInit).headers).has("Authorization")).toBe(false);
    expect(publicPlaceHref("instituição central", "space", "codigo-estavel"))
      .toBe("/p/institui%C3%A7%C3%A3o%20central/locais/space/codigo-estavel");
  });

  it("envia uma foto como multipart preservando o boundary gerado pelo navegador", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 201, json: async () => ({ id: "foto-1" }) } as Response);
    const file = new File(["foto"], "fachada.jpg", { type: "image/jpeg" });

    await geoCampusApi.photos.upload("campus-1", "building", "bloco-1", file, " Entrada principal ");

    const [url, init] = fetchMock.mock.calls[0];
    const options = init as RequestInit;
    expect(url).toBe("http://localhost:8000/campuses/campus-1/places/building/bloco-1/photos");
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer admin-token");
    expect(new Headers(options.headers).has("Content-Type")).toBe(false);
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toEqual(file);
    expect((options.body as FormData).get("caption")).toBe("Entrada principal");
  });

  it("carrega o conteúdo de uma foto administrativa com autenticação", async () => {
    const photo = new Blob(["foto"], { type: "image/jpeg" });
    fetchMock.mockResolvedValue({ ok: true, status: 200, blob: async () => photo } as Response);

    const result = await geoCampusApi.photos.content("campus-1", "landmark", "praca-1", "foto-1");

    expect(result).toBe(photo);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/campuses/campus-1/places/landmark/praca-1/photos/foto-1");
    expect(new Headers((init as RequestInit).headers).get("Authorization")).toBe("Bearer admin-token");
    expect(campusPhotoUrl("/public/instituicao/places/landmark/praca-1/photos/foto-1"))
      .toBe("http://localhost:8000/public/instituicao/places/landmark/praca-1/photos/foto-1");
  });
});

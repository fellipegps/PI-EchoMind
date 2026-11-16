import { expect, test } from "@playwright/test";

const slug = "ds04-fixture";
const campus = { id: "campus-visual", name: "Campus de teste", description: null, center_lat: -23.55, center_lng: -46.63, zoom: 17, active: true };
const building = { id: "bloco-a", campus_id: campus.id, public_code: "bloco-estavel", name: "Bloco A", description: "Fachada de tijolos junto à praça.", category: "bloco", entrance_lat: -23.55, entrance_lng: -46.63, active: true, photos: [] };
const space = {
  id: "lab-1", campus_id: campus.id, public_code: "laboratorio-estavel", building_id: building.id,
  name: "Laboratório de informática", description: "Porta azul, ao lado do auditório.", kind: "laboratorio", floor: "1º andar", active: true,
  photos: ["Porta de entrada", "Vista do corredor"].map((caption, index) => ({
    id: `foto-${index}`, caption, sort_order: index,
    url: `/public/${slug}/places/space/laboratorio-estavel/photos/foto-${index}`,
  })),
};
const landmark = { id: "praca", campus_id: campus.id, public_code: "praca-estavel", name: "Praça central", description: "Jardim com bancos.", lat: -23.5502, lng: -46.6302, active: true, photos: [] };
const spacePath = `/p/${slug}/locais/space/${space.public_code}`;
const pixel = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1EAAAAASUVORK5CYII=", "base64");

test("o mapa e o link do QR abrem a mesma ficha com fotos e identificação do bloco", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    window.locationRequests = 0;
    const request = () => { window.locationRequests += 1; };
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition: request, watchPosition: request, clearWatch() {} },
    });
  });
  await page.route("**/public/ds04-fixture/geo-campus", (route) => route.fulfill({
    json: { campuses: [campus], buildings: [building], spaces: [space], landmarks: [landmark] },
  }));
  await page.route("**/public/ds04-fixture/places/**", async (route) => {
    expect(route.request().headers().authorization).toBeUndefined();
    const path = new URL(route.request().url()).pathname;
    if (path.includes("/photos/")) {
      await route.fulfill({ contentType: "image/png", body: pixel });
      return;
    }
    const type = path.split("/")[4];
    const place = { building, space, landmark }[type];
    await route.fulfill({ json: { type, campus, place, building: type === "space" ? building : null } });
  });
  await page.route("**/tile.openstreetmap.org/**", (route) => route.fulfill({ contentType: "image/png", body: pixel }));
  await page.route("**/test-satellite/**", (route) => route.fulfill({ contentType: "image/png", body: pixel }));

  await page.goto(`/p/${slug}?tab=locais`, { waitUntil: "domcontentloaded" });
  const local = page.getByRole("link", { name: /Laboratório de informática/ });
  await expect(local).toHaveAttribute("href", spacePath);
  await expect(page.getByRole("link", { name: "Ver ficha de Praça central" })).toBeVisible();
  await expect(page.getByRole("button", { name: /usar minha localização|calcular rota/i })).toHaveCount(0);
  expect(await page.evaluate(() => window.locationRequests)).toBe(0);
  await local.click();

  await expect(page).toHaveURL(new RegExp(`${spacePath}$`), { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: space.name, exact: true })).toBeVisible();
  await expect(page.getByText(space.description)).toBeVisible();
  await expect(page.getByRole("link", { name: building.name, exact: true })).toHaveAttribute("href", `/p/${slug}/locais/building/${building.public_code}`);
  await expect(page.getByRole("img", { name: "Porta de entrada", exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: "Vista do corredor", exact: true })).toBeVisible();

  // Acesso direto reproduz o endereço lido no QR impresso.
  await page.goto(spacePath, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: space.name, exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: "Vista do corredor", exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.locationRequests)).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("link", { name: "Voltar aos locais do campus" }).click();
  await expect(local).toBeVisible();
});

test("bloco vinculado e ponto cadastrado exibem as mesmas fotos na maquete e no satélite", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1280, height: 900 });
  const modelKey = "validacao-maquete";
  const modelCampus = { ...campus, model_key: modelKey };
  const block = {
    ...building, name: "Bloco de Saúde", model_destination_id: "bloco-a",
    photos: [{ id: "fachada", caption: "Fachada do Bloco A", sort_order: 0,
      url: '/public/' + slug + '/places/building/' + building.public_code + '/photos/fachada' }],
  };
  const internal = { ...space, name: "Laboratório de Saúde", description: "Use o elevador da recepção." };
  const point = {
    ...landmark, lat: -23.5502, lng: -46.62934,
    photos: [{ id: "jardim", caption: "Vista do jardim", sort_order: 0,
      url: '/public/' + slug + '/places/landmark/' + landmark.public_code + '/photos/jardim' }],
  };

  await page.route("**/public/ds04-fixture/geo-campus", (route) => route.fulfill({
    json: { campuses: [modelCampus], buildings: [block], spaces: [internal],
      landmarks: [point, { ...point, id: "oculto", name: "Ponto oculto", active: false }] },
  }));
  await page.route("**/public/ds04-fixture/places/**/photos/**", (route) =>
    route.fulfill({ contentType: "image/png", body: pixel }));
  await page.route("**/test-satellite/**", (route) => route.fulfill({ contentType: "image/png", body: pixel }));
  await page.route("**/campus-guide/" + modelKey + "/destinations.json", (route) => route.fulfill({
    json: { sources: {}, aboutSources: [], destinations: [{
      id: "bloco-a", name: "Nome no arquivo", shortName: "A", kind: "Bloco",
      labelCoordinates: [-46.63, -23.55], entry: { coordinates: [-46.63, -23.55015], status: "confirmed" },
    }] },
  }));
  await page.route("**/campus-guide/" + modelKey + "/buildings.geojson", (route) => route.fulfill({
    json: { type: "FeatureCollection", features: [{
      type: "Feature", id: "bloco-a", properties: { kind: "destination", heightMeters: 14 },
      geometry: { type: "Polygon", coordinates: [[
        [-46.6302, -23.55015], [-46.6298, -23.55015], [-46.6298, -23.54985],
        [-46.6302, -23.54985], [-46.6302, -23.55015],
      ]] },
    }] },
  }));
  await page.route("**/campus-guide/" + modelKey + "/context.geojson", (route) => route.fulfill({
    json: { type: "FeatureCollection", features: [] },
  }));

  await page.goto(`/p/${slug}?tab=locais`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "Maquete 3D" })).toBeEnabled();
  const map = page.getByRole("region", { name: "Mapa interativo do campus" });
  const photos = async (place, label, type) => {
    const panel = map.getByRole("region", { name: place.name, exact: true });
    await expect(panel).toBeVisible();
    const photo = panel.getByRole("img", { name: label });
    await expect(photo).toBeVisible();
    await expect.poll(() => photo.evaluate((image) => image.naturalWidth)).toBeGreaterThan(0);
    await expect(panel.getByRole("link", { name: "Abrir ficha completa" }))
      .toHaveAttribute("href", '/p/' + slug + '/locais/' + type + '/' + place.public_code);
  };

  await map.getByRole("button", { name: block.name, exact: true }).click();
  await photos(block, "Fachada do Bloco A", "building");
  await expect(map.getByText(internal.description)).toBeVisible();
  await map.getByRole("button", { name: "Satélite" }).click();
  await photos(block, "Fachada do Bloco A", "building");
  await expect(map.getByRole("link", { name: /Laboratório de Saúde/ })).toHaveAttribute("href", spacePath);
  await expect.poll(() => map.locator(".satellite-imagery img").evaluateAll(
    (tiles) => tiles.some((tile) => tile.naturalWidth > 0),
  )).toBe(true);

  await page.getByRole("button", { name: "Locais", exact: true }).click();
  await page.getByRole("button", { name: "Ver no mapa: Praça central" }).click();
  await photos(point, "Vista do jardim", "landmark");
  await expect(map.getByRole("button", { name: point.name, exact: true })).toHaveAttribute("aria-pressed", "true");
  await map.getByRole("button", { name: "Maquete 3D" }).click();
  await photos(point, "Vista do jardim", "landmark");
  await expect(map.getByRole("button", { name: "Ponto oculto" })).toHaveCount(0);
});

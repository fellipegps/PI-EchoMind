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

  await page.goto(`/p/${slug}?tab=locais`);
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
  await page.goto(spacePath);
  await expect(page.getByRole("heading", { name: space.name, exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: "Vista do corredor", exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.locationRequests)).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("link", { name: "Voltar aos locais do campus" }).click();
  await expect(local).toBeVisible();
});

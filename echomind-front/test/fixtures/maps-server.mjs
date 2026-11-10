// Local fixtures for the public visual campus guide.
import { createServer } from "node:http";
import { testPrivacySettings } from "./privacy-settings.mjs";
import { appendFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const logPath = fileURLToPath(new URL("../../.next/ds06-requests.jsonl", import.meta.url));
mkdirSync(fileURLToPath(new URL("../../.next", import.meta.url)), { recursive: true });
const lat = -23.5505, lng = -46.6333;
const campuses = [
  { id: "c1", name: "Campus de teste Centro", description: null, center_lat: lat, center_lng: lng, zoom: 18, active: true },
  { id: "c2", name: "Campus de teste Norte", description: null, center_lat: lat + 0.001, center_lng: lng + 0.001, zoom: 18, active: true },
];
const buildings = [
  { id: "block", campus_id: "c1", public_code: "11111111-1111-4111-8111-111111111111", name: "Bloco A", description: "Ensino e pesquisa · dados fictícios", category: "ensino", entrance_lat: lat, entrance_lng: lng, active: true, photos: [] },
  { id: "north", campus_id: "c2", public_code: "22222222-2222-4222-8222-222222222222", name: "Biblioteca Norte", description: "Somente segundo campus", category: "biblioteca", entrance_lat: lat + 0.001, entrance_lng: lng + 0.001, active: true, photos: [] },
];
const spaces = [{ id: "lab", campus_id: "c1", public_code: "33333333-3333-4333-8333-333333333333", building_id: "block", name: "Laboratório de Química", kind: "laboratório", floor: "1º andar", description: "Ala leste · espaço fictício", active: true, photos: [] }];
const landmarks = [{ id: "square", campus_id: "c1", public_code: "44444444-4444-4444-8444-444444444444", name: "Praça central", description: "Ponto de referência junto ao jardim.", lat: lat + 0.0001, lng: lng + 0.0002, active: true, photos: [] }];
const samplePng = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aocEAAAAASUVORK5CYII=", "base64");

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  const path = new URL(req.url, "http://127.0.0.1:4109").pathname;
  appendFileSync(logPath, JSON.stringify({ method: req.method, path }) + "\n");
  const match = path.match(/^\/public\/(ds06-fixture|ds06-disconnected|ds06-long|ds06-error|ds06-empty|ds06-loading)(\/[^?]*)?$/);
  if (!match) { res.writeHead(404); res.end("{}"); return; }
  const [, slug, suffix = ""] = match;
  if (slug === "ds06-loading" && suffix === "/geo-campus") await new Promise(resolve => setTimeout(resolve, 6000));
  if (slug === "ds06-error" && suffix === "/geo-campus") { res.writeHead(500); res.end(JSON.stringify({ detail: "detalhe interno de teste" })); return; }
  const long = "Nome extenso de teste para verificar a leitura completa de blocos, espaços e referências " + "TextoExtenso".repeat(8);
  const withPhotos = (item, type) => ({ ...item, photos: [
    { id: `${item.id}-entry`, caption: "Entrada do local", sort_order: 0, url: `/public/${slug}/places/${type}/${item.public_code}/photos/entrada` },
    { id: `${item.id}-front`, caption: "Fachada de referência", sort_order: 1, url: `/public/${slug}/places/${type}/${item.public_code}/photos/fachada` },
  ] });
  const geo = {
    campuses,
    buildings: buildings.map(item => withPhotos(slug === "ds06-long" ? { ...item, name: item.name + " · " + long, description: long } : item, "building")),
    spaces: spaces.map(item => withPhotos(item, "space")),
    landmarks: landmarks.map(item => withPhotos(item, "landmark")),
  };
  const placeMatch = suffix.match(/^\/places\/(building|space|landmark)\/([^/]+)(\/photos\/[^/]+)?$/);
  if (placeMatch) {
    const [, type, code, photo] = placeMatch;
    const place = ({ building: geo.buildings, space: geo.spaces, landmark: geo.landmarks })[type].find(item => item.public_code === code);
    if (!place || slug === "ds06-empty") { res.writeHead(404); res.end("{}"); return; }
    if (photo) { res.setHeader("Content-Type", "image/png"); res.end(samplePng); return; }
    res.end(JSON.stringify({ type, campus: campuses.find(item => item.id === place.campus_id), place, building: type === "space" ? geo.buildings.find(item => item.id === place.building_id) : null }));
    return;
  }
  const responses = {
    "": { ...testPrivacySettings, public_slug: slug, company_name: "Campus fictício · DS-06", website: null, phone: null, address: null, business_hours: null },
    "/faqs": [], "/events": [],
    "/geo-campus": slug === "ds06-empty" ? { campuses: [], buildings: [], spaces: [], landmarks: [] } : geo,
  };
  if (suffix in responses) { res.end(JSON.stringify(responses[suffix])); return; }
  res.writeHead(404); res.end("{}");
}).listen(4109, "127.0.0.1", () => console.log("DS-06 fixtures: http://127.0.0.1:4109 (local only)"));

// DS-06: synthetic data only, no upstream API, credentials or real location.
import { createServer } from "node:http";
import { appendFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const logPath = fileURLToPath(new URL("../../.next/ds06-requests.jsonl", import.meta.url));
mkdirSync(fileURLToPath(new URL("../../.next", import.meta.url)), { recursive: true });
const lat = -23.5505, lng = -46.6333;
const campuses = [{ id: "c1", name: "Campus de teste Centro", description: null, center_lat: lat + 0.00005, center_lng: lng + 0.00005, zoom: 18, active: true }, { id: "c2", name: "Campus de teste Norte", description: null, center_lat: lat + 0.001, center_lng: lng + 0.001, zoom: 18, active: true }, { id: "hidden", name: "Campus inativo", active: false }];
const nodes = [
  { id: "a", campus_id: "c1", lat, lng, label: "Portaria" },
  { id: "b", campus_id: "c1", lat, lng: lng + 0.0001, label: "Praça" },
  { id: "c", campus_id: "c1", lat: lat + 0.0001, lng, label: "Rampa" },
  { id: "d", campus_id: "c1", lat: lat + 0.0001, lng: lng + 0.0001, label: "Bloco A" },
  { id: "n", campus_id: "c2", lat: lat + 0.001, lng: lng + 0.001, label: "Entrada Norte" },
];
const buildings = [
  { id: "gate", campus_id: "c1", name: "Portaria", description: "Acesso fictício", category: "acesso", entrance_lat: lat, entrance_lng: lng, entrance_node_id: "a", active: true },
  { id: "block", campus_id: "c1", name: "Bloco A", description: "Ensino e pesquisa · dados fictícios", category: "ensino", entrance_lat: lat + 0.0001, entrance_lng: lng + 0.0001, entrance_node_id: "d", active: true },
  { id: "unlinked", campus_id: "c1", name: "Prédio sem entrada vinculada", description: "Estado de teste", category: "ensino", entrance_lat: lat - 0.0001, entrance_lng: lng + 0.0002, entrance_node_id: null, active: true },
  { id: "far", campus_id: "c1", name: "Prédio com entrada distante", description: "Estado de teste", category: "ensino", entrance_lat: lat + 0.001, entrance_lng: lng + 0.001, entrance_node_id: "d", active: true },
  { id: "north", campus_id: "c2", name: "Biblioteca Norte", description: "Somente segundo campus", category: "biblioteca", entrance_lat: lat + 0.001, entrance_lng: lng + 0.001, entrance_node_id: "n", active: true },
  { id: "inactive", campus_id: "c1", name: "Prédio inativo", active: false },
];
const spaces = [{ id: "lab", campus_id: "c1", building_id: "block", name: "Laboratório de Química", kind: "laboratório", floor: "1º andar", description: "Ala leste · espaço fictício", active: true }];
const edges = [
  { id: "ab", campus_id: "c1", from_node_id: "a", to_node_id: "b", distance_m: 10, accessible: false, active: true },
  { id: "bd", campus_id: "c1", from_node_id: "b", to_node_id: "d", distance_m: 10, accessible: true, active: true },
  { id: "ac", campus_id: "c1", from_node_id: "a", to_node_id: "c", distance_m: 16, accessible: true, active: true },
  { id: "cd", campus_id: "c1", from_node_id: "c", to_node_id: "d", distance_m: 16, accessible: true, active: true },
];
const locations = Array.from({ length: 8 }, (_, i) => ({ id: `local-${i}`, name: `Local de teste ${i + 1}`, description: "Descrição fictícia", category: "ensino", building: "Bloco de teste", floor: "Térreo", x: 20 + (i % 4) * 20, y: 30 + Math.floor(i / 4) * 35 }));
createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS");
  if (req.method === "OPTIONS") { res.writeHead(204);res.end();return; }
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  const path = new URL(req.url, "http://127.0.0.1:4109").pathname;
  appendFileSync(logPath, JSON.stringify({ method: req.method, path }) + "\n");
  const match = path.match(/^\/public\/(ds06-fixture|ds06-schematic|ds06-disconnected|ds06-long|ds06-error|ds06-empty|ds06-loading)(\/[^?]*)?$/);
  if (!match) { res.writeHead(404);res.end("{}");return; }
  const [, slug, suffix = ""] = match;
  if (slug === "ds06-loading" && ["/locations", "/geo-campus"].includes(suffix)) await new Promise(resolve => setTimeout(resolve, 6000));
  if (slug === "ds06-error" && ["/locations", "/geo-campus"].includes(suffix)) {res.writeHead(500);res.end(JSON.stringify({ detail: "detalhe interno de teste" }));return;}
  const long = "Nome extenso de teste para verificar a leitura completa de prédios, espaços, descrições e controles " + "TextoExtenso".repeat(8);
  const geo = { campuses, buildings: slug === "ds06-long" ? buildings.map(b => ({...b, name: b.name + " · " + long, description: long })) : buildings,
    spaces: slug === "ds06-long" ? spaces.map(s => ({...s, name: s.name + " · " + long, floor: "Andar de teste com identificação extensa", description: long })) : spaces,
    nodes, edges: slug === "ds06-disconnected" ? [] : edges };
  const responses = {
    "": { public_slug: slug, company_name: "Campus fictício · DS-06", website: null, phone: null, address: null, business_hours: null },
    "/faqs": [], "/events": [],
    "/locations": slug === "ds06-empty" ? [] : slug === "ds06-long" ? locations.map(l=>({...l,name:l.name+" · "+long,building:long,floor:long})) : locations,
    "/geo-campus": ["ds06-schematic","ds06-empty"].includes(slug) ? { campuses: [], buildings: [], spaces: [], nodes: [], edges: [] } : geo,
  };
  if (suffix in responses) {res.end(JSON.stringify(responses[suffix]));return;}
  res.writeHead(404);res.end("{}");
}).listen(4109,"127.0.0.1",()=>console.log("DS-06 fixtures: http://127.0.0.1:4109 (local only)"));

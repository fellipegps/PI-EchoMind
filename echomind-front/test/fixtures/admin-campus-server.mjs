// DS-14: disposable geographic data, auth and synthetic tiles. Loopback only; no upstream.
import { createServer } from "node:http";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const directory = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(directory, { recursive: true });
const control = `${directory}/ds14-control.json`;
writeFileSync(control, JSON.stringify({ mode: "ready", hold: null, revision: 0 }));
const config = () => JSON.parse(readFileSync(control, "utf8"));
const user = { id: "00000000-0000-4000-8000-000000000014", email: "ds14@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-12T00:00:00Z" };
const initial = () => ({
  campuses: [
    { id: "central", name: "Campus Central sintético", description: "Área fictícia", center_lat: -16.328, center_lng: -48.953, zoom: 18, active: true },
    { id: "north", name: "Campus Norte sintético", description: null, center_lat: -16.33, center_lng: -48.96, zoom: 18, active: false },
  ],
  buildings: [
    { id: "library", campus_id: "central", name: "Biblioteca sintética", category: "estudo", description: "Acervo fictício", entrance_lat: -16.328, entrance_lng: -48.953, entrance_node_id: "gate", active: true },
    { id: "unlinked", campus_id: "central", name: "Bloco sem rota", category: "ensino", description: null, entrance_lat: -16.3284, entrance_lng: -48.9537, entrance_node_id: null, active: false },
    { id: "long", campus_id: "central", name: "Prédio extenso: " + "NomeSemEspacos".repeat(12), category: "Categoria".repeat(8), description: "Descrição fictícia extensa. ".repeat(90), entrance_lat: -16.3278, entrance_lng: -48.9535, entrance_node_id: "ramp", active: true },
    { id: "north-building", campus_id: "north", name: "Bloco exclusivo Norte", category: "ensino", description: null, entrance_lat: -16.33, entrance_lng: -48.96, entrance_node_id: "north-gate", active: true },
  ],
  spaces: [{ id: "lab", campus_id: "central", building_id: "library", name: "Laboratório sintético", kind: "laboratório", floor: "2º andar", description: "Espaço fictício", active: true }],
  "path-nodes": [
    { id: "gate", campus_id: "central", label: "Portaria", lat: -16.328, lng: -48.953 },
    { id: "square", campus_id: "central", label: "Praça", lat: -16.3283, lng: -48.953 },
    { id: "ramp", campus_id: "central", label: "Rampa", lat: -16.3283, lng: -48.9534 },
    { id: "north-gate", campus_id: "north", label: "Entrada Norte", lat: -16.33, lng: -48.96 },
  ],
  "path-edges": [
    { id: "accessible", campus_id: "central", from_node_id: "gate", to_node_id: "square", distance_m: 35, accessible: true, active: true },
    { id: "barrier", campus_id: "central", from_node_id: "square", to_node_id: "ramp", distance_m: 43, accessible: false, active: true },
    { id: "inactive", campus_id: "central", from_node_id: "gate", to_node_id: "ramp", distance_m: null, accessible: true, active: false },
  ],
});
let data = initial(), revision = 0, sequence = 0;
createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*"); res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS"); res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const url = new URL(req.url, "http://127.0.0.1:4181"); let cfg = config();
  if (cfg.revision !== revision) { data = initial(); revision = cfg.revision; }
  if (/^\/(tiles|sat)\//.test(url.pathname)) {
    res.setHeader("Content-Type", "image/svg+xml");
    res.end(`<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="${url.pathname.startsWith("/sat/") ? "#c4d5b7" : "#e4e8e0"}"/><path d="M0 128H256M128 0V256" stroke="#fff" stroke-width="14"/><path d="M0 128H256M128 0V256" stroke="#a7b89e" stroke-width="2"/><text x="12" y="30" font-family="sans-serif" font-size="14" fill="#37452f">DS-14 · tile fictício</text></svg>`); return;
  }
  const record = { id: ++sequence, method: req.method, path: url.pathname, mode: cfg.mode, hold: cfg.hold, authenticated: !!req.headers.authorization, startedAt: Date.now() };
  const log = entry => appendFileSync(`${directory}/ds14-requests.jsonl`, JSON.stringify(entry) + "\n"); log(record);
  if (url.pathname === "/auth/v1/token") {
    let raw = ""; for await (const chunk of req) raw += chunk; const body = JSON.parse(raw || "{}");
    if (body.email !== user.email || body.password !== "DS14-test-only") { res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant" })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds14-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (url.pathname === "/auth/v1/user") { res.end(JSON.stringify(user)); return; }
  if (url.pathname === "/auth/me") { res.end(JSON.stringify({ ...user, is_active: true })); return; }
  if (url.pathname === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }
  if (url.pathname === "/dashboard") { res.end(JSON.stringify({ total_questions: 0, unanswered_questions: 0, avg_response_time: "0 s", satisfaction_rate: 0, daily_interactions: [], top_faqs: [] })); return; }
  if (url.pathname === "/dashboard/rag-metrics") { res.end(JSON.stringify({ has_data: false })); return; }
  const match = url.pathname.match(/^\/campuses(?:\/([^/]+))?(?:\/(buildings|spaces|path-nodes|path-edges)(?:\/([^/]+))?)?$/);
  if (match) {
    if (!req.headers.authorization) { res.writeHead(401); res.end("{}"); return; }
    const [, campusId, resource, itemId] = match; const key = resource || "campuses";
    let raw = ""; for await (const chunk of req) raw += chunk; const body = JSON.parse(raw || "{}");
    const operation = req.method === "GET" ? "list" : req.method === "POST" ? "create" : req.method === "PUT" ? "update" : "delete";
    // A held list captures its old response, so release can exercise out-of-order delivery.
    const snapshot = data[key].filter(item => !resource || item.campus_id === campusId);
    for (let i = 0; [operation, `list-${campusId}`].includes(config().hold) && i < 2400; i++) await new Promise(resolve => setTimeout(resolve, 250));
    cfg = config();
    const send = (status, value) => { log({ ...record, completed: true, status, endedAt: Date.now(), ...(req.method !== "GET" ? { payload: body } : {}) }); res.writeHead(status); res.end(status === 204 ? undefined : JSON.stringify(value)); };
    if (cfg.mode === `${operation}-error` || (cfg.mode === "campuses-error" && key === "campuses") || (cfg.mode === "map-error" && resource)) { send(500, { detail: "SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR" }); return; }
    if (cfg.mode === "delete-conflict" && operation === "delete") { send(409, { detail: "Cadastro possui vínculos. Remova as ligações antes de excluir." }); return; }
    if (operation === "list") { send(200, cfg.mode === "empty" ? [] : snapshot); return; }
    if (operation === "create") { const created = { ...body, id: `${key}-created-${sequence}`, ...(resource ? { campus_id: campusId } : {}) }; data[key].push(created); send(201, created); return; }
    const index = data[key].findIndex(item => item.id === (resource ? itemId : campusId));
    if (index < 0) { send(404, { detail: "Cadastro sintético ausente" }); return; }
    if (operation === "update") { data[key][index] = { ...data[key][index], ...body }; send(200, data[key][index]); return; }
    data[key].splice(index, 1); send(204); return;
  }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Fora da fixture DS-14" }));
}).listen(4181, "127.0.0.1", () => console.log("DS-14 fixture ready at http://127.0.0.1:4181"));

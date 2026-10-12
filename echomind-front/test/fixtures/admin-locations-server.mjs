// DS-13: disposable schematic locations and authentication, loopback only; no upstream.
import { createServer } from "node:http";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const directory = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(directory, { recursive: true });
const control = `${directory}/ds13-control.json`;
writeFileSync(control, JSON.stringify({ mode: "ready", hold: null, revision: 0 }));
const config = () => JSON.parse(readFileSync(control, "utf8"));
const user = { id: "00000000-0000-4000-8000-000000000013", email: "ds13@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-12T00:00:00Z" };
const initial = () => [
  { id: "location-alpha", name: "Biblioteca sintética", category: "estudo", building: "Bloco B", floor: "Térreo", description: "Acervo fictício para teste.", x: 30.7, y: 40.3, active: true },
  { id: "location-beta", name: "Cantina sintética", category: "alimentação", building: "Bloco A", floor: "Superior", description: null, x: 12.1, y: 95.9, active: false },
  { id: "location-long", name: "Local extenso: " + "NomeSemEspacos".repeat(13), category: "Categoria".repeat(10), building: "Bloco".repeat(20), floor: "Piso".repeat(12), description: "Descrição sintética longa. ".repeat(70), x: 88.8, y: 1.2, active: true },
].map(item => ({ ...item, created_at: "2026-10-12T12:00:00Z", updated_at: "2026-10-12T12:00:00Z" }));
let locations = initial(), revision = 0, sequence = 0;
createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const url = new URL(req.url, "http://127.0.0.1:4171");
  let cfg = config();
  if (cfg.revision !== revision) { locations = initial(); revision = cfg.revision; }
  const record = { id: ++sequence, method: req.method, path: url.pathname, mode: cfg.mode, hold: cfg.hold, authenticated: !!req.headers.authorization, startedAt: Date.now() };
  const log = data => appendFileSync(`${directory}/ds13-requests.jsonl`, JSON.stringify(data) + "\n");
  log(record);
  if (url.pathname === "/auth/v1/token") {
    let raw = ""; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    if (body.email !== user.email || body.password !== "DS13-test-only") { res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant" })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds13-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (url.pathname === "/auth/v1/user") { res.end(JSON.stringify(user)); return; }
  if (url.pathname === "/auth/me") { res.end(JSON.stringify({ ...user, is_active: true })); return; }
  if (url.pathname === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }
  if (url.pathname === "/dashboard") { res.end(JSON.stringify({ total_questions: 0, unanswered_questions: 0, avg_response_time: "0 s", satisfaction_rate: 0, daily_interactions: [], top_faqs: [] })); return; }
  if (url.pathname === "/dashboard/rag-metrics") { res.end(JSON.stringify({ has_data: false })); return; }
  if (url.pathname.startsWith("/locations")) {
    let raw = ""; for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    const operation = req.method === "GET" ? "list" : req.method === "POST" ? "create" : req.method === "PUT" ? "update" : "delete";
    for (let i = 0; config().hold === operation && i < 2400; i++) await new Promise(resolve => setTimeout(resolve, 250));
    cfg = config();
    const send = (status, data) => { log({ ...record, completed: true, status, endedAt: Date.now(), ...(req.method !== "GET" ? { payload: body } : {}) }); res.writeHead(status); res.end(status === 204 ? undefined : JSON.stringify(data)); };
    if (cfg.mode === `${operation}-error`) { send(500, { detail: "SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR" }); return; }
    if (operation === "list") { send(200, cfg.mode === "empty" ? [] : locations); return; }
    if (operation === "create") { const created = { ...body, id: `location-created-${sequence}`, created_at: "2026-10-12T12:00:00Z", updated_at: "2026-10-12T12:00:00Z" }; locations.push(created); send(201, created); return; }
    const index = locations.findIndex(item => item.id === url.pathname.split("/")[2]);
    if (index < 0) { send(404, { detail: "Local sintético ausente" }); return; }
    if (operation === "update") { locations[index] = { ...locations[index], ...body }; send(200, locations[index]); return; }
    if (operation === "delete") { locations.splice(index, 1); send(204); return; }
  }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Fora da fixture DS-13" }));
}).listen(4171, "127.0.0.1", () => console.log("DS-13 fixture ready at http://127.0.0.1:4171"));

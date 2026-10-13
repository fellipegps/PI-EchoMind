// DS-15: disposable auth, plain-text streaming and configuration. Loopback only.
import { createServer } from "node:http";
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const directory = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(directory, { recursive: true });
const control = `${directory}/ds15-control.json`;
writeFileSync(control, JSON.stringify({ mode: "ready", hold: null }));
const settings = () => JSON.parse(readFileSync(control, "utf8"));
const user = { id: "00000000-0000-4000-8000-000000000015", email: "ds15@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-12T00:00:00Z" };
const initial = {
  id: "internal-config-id", public_slug: "instituicao-sintetica-" + "campus-extenso-".repeat(7) + "central",
  company_name: "Instituição sintética de ensino, pesquisa e extensão — unidade de demonstração",
  description: "Contexto fictício para verificação visual e funcional. ".repeat(30),
  tone_of_voice: "profissional e cordial", chat_voice_gender: "feminina",
  website: "https://example.test/" + "endereco-sem-espacos-".repeat(10), phone: "(00) 00000-0000",
  address: "Avenida fictícia, 1000 — Setor de demonstração, Cidade de teste", business_hours: "Segunda a sexta, das 8h às 22h; sábado das 8h às 12h", updated_at: null,
};
let config = { ...initial }, sequence = 0;
const pause = () => new Promise(resolve => setTimeout(resolve, 100));
async function held(stage) { for (let i = 0; settings().hold === stage && i < 3000; i++) await pause(); }

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*"); res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS"); res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const url = new URL(req.url, "http://127.0.0.1:4191");
  const record = { id: ++sequence, method: req.method, path: url.pathname, mode: settings().mode, authenticated: !!req.headers.authorization, startedAt: Date.now() };
  const log = entry => appendFileSync(`${directory}/ds15-requests.jsonl`, JSON.stringify(entry) + "\n");
  log(record);
  const send = (status, body, payload) => { log({ ...record, completed: true, status, ...(payload ? { payload } : {}) }); res.writeHead(status); res.end(JSON.stringify(body)); };
  let raw = ""; for await (const chunk of req) raw += chunk;
  const body = JSON.parse(raw || "{}");
  if (url.pathname === "/auth/v1/token") {
    if (body.email !== user.email || body.password !== "DS15-test-only") { send(400, { error: "invalid_grant" }); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    send(200, { access_token: jwt, refresh_token: "ds15-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user }); return;
  }
  if (url.pathname === "/auth/v1/user") { send(200, user); return; }
  if (url.pathname === "/auth/me") { send(200, { ...user, is_active: true }); return; }
  if (url.pathname === "/dashboard") { send(200, { total_questions: 0, unanswered_questions: 0, avg_response_time: "0 s", satisfaction_rate: 0, daily_interactions: [], top_faqs: [] }); return; }
  if (url.pathname === "/dashboard/rag-metrics") { send(200, { has_data: false }); return; }
  if (url.pathname === "/chat") {
    log({ ...record, payload: body });
    if (body.tenant_id !== user.id) { send(400, { detail: "Contexto incorreto" }); return; }
    if (settings().mode === "chat-error") { send(503, { detail: "docker: falha sintética" }); return; }
    res.setHeader("Content-Type", "text/plain; charset=utf-8"); res.flushHeaders();
    await held("chat-first");
    if (settings().mode === "chat-empty") { log({ ...record, completed: true, status: 200, empty: true }); res.end(); return; }
    const first = "Resposta parcial: "; res.write(first);
    await held("chat-done");
    const rest = '<img src=x onerror=alert(1)>\n**Texto literal**\n' + "Mensagem extensa sem espaços: " + "SemEspacos".repeat(90) + "\n" + "Linha de teste preservada.\n".repeat(18);
    res.end(rest); log({ ...record, completed: true, status: 200, expectedText: first + rest }); return;
  }
  if (url.pathname === "/config") {
    if (!req.headers.authorization) { send(401, {}); return; }
    if (req.method === "GET") {
      await held("load");
      if (settings().mode === "load-error") { send(404, { detail: "Configuração sintética ausente" }); return; }
      send(200, { ...config, ...(settings().mode === "no-slug" ? { public_slug: "" } : {}) }); return;
    }
    if (req.method === "PUT") {
      await held("save");
      if (settings().mode === "save-error") { send(503, { detail: "Falha sintética ao salvar" }, body); return; }
      config = { ...config, ...body, company_name: body.company_name.trim() + " · retorno da API", public_slug: "instituicao-atualizada", updated_at: "2026-10-12T23:00:00Z" };
      send(200, config, body); return;
    }
  }
  if (/^\/public\/[^/]+$/.test(url.pathname)) { send(200, { public_slug: config.public_slug, company_name: config.company_name, description: config.description }); return; }
  send(404, { detail: "Fora da fixture DS-15" });
}).listen(4191, "127.0.0.1", () => console.log("DS-15 fixture ready at http://127.0.0.1:4191"));

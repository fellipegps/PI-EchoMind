// DS-09: synthetic session and in-memory FAQ data on loopback only. No upstream calls.
import { createServer } from "node:http";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const directory = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(directory, { recursive: true });
const control = `${directory}/ds09-control.json`;
writeFileSync(control, JSON.stringify({ mode: "ready", hold: null, revision: 0 }));
const config = () => JSON.parse(readFileSync(control, "utf8"));
const user = { id: "00000000-0000-4000-8000-000000000009", email: "ds09@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-12T00:00:00Z" };
const stamp = "2026-10-12T12:00:00Z";
const question = "Como consultar os procedimentos institucionais de MATRÍCULA, transferência e bolsas de estudo, incluindo prazos, documentos obrigatórios e atendimento aos estudantes de outros campi?";
const answer = "Resposta fictícia: consulte a secretaria acadêmica para conferir os procedimentos e os prazos do próximo semestre.\nEste texto conserva parágrafos, acentos e uma referência extensa sem espaços para verificar a leitura integral: " + "ReferenciaInstitucional".repeat(9) + ".";
const initial = () => [question, "Qual é o horário da biblioteca?", "Como solicitar atendimento acadêmico?", "Onde consultar os documentos institucionais?", "Como localizar os espaços do campus?"].map((question, i) => ({ id: `faq-${i + 1}`, question, answer: i === 0 ? answer : "Resposta sintética para teste de gestão de FAQs.", show_in_chatbot: i > 0, created_at: stamp }));
let faqs = initial();
let revision = 0;
let sequence = 6;

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
  res.setHeader("Content-Type", "application/json");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const url = new URL(req.url, "http://127.0.0.1:4131");
  let cfg = config();
  if (cfg.revision !== revision) { faqs = initial(); revision = cfg.revision; sequence = 6; }
  const record = { method: req.method, path: url.pathname, mode: cfg.mode, hold: cfg.hold, authenticated: !!req.headers.authorization };
  appendFileSync(`${directory}/ds09-requests.jsonl`, JSON.stringify(record) + "\n");
  if (url.pathname === "/auth/v1/token") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    if (body.email !== user.email || body.password !== "DS09-test-only") { res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant" })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds09-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (url.pathname === "/auth/v1/user") { res.end(JSON.stringify(user)); return; }
  if (url.pathname === "/auth/me") { res.end(JSON.stringify({ ...user, is_active: true })); return; }
  if (url.pathname === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }

  if (url.pathname === "/documents") { res.end(JSON.stringify({ documents: [], total: 0 })); return; }
  if (url.pathname === "/documents/upload-limits") { res.end(JSON.stringify({ max_document_size_bytes: 10485760 })); return; }
  if (url.pathname.startsWith("/faqs")) {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    const operation = req.method === "GET" ? "list" : req.method === "DELETE" ? "delete" : req.method === "PATCH" ? "toggle" : "save";
    for (let i = 0; config().hold === operation && i < 2400; i++) await new Promise(resolve => setTimeout(resolve, 250));
    cfg = config();
    const send = (status, data) => {
      appendFileSync(`${directory}/ds09-requests.jsonl`, JSON.stringify({ ...record, completed: true, status, ...(operation === "save" ? { payload: body } : {}) }) + "\n");
      res.writeHead(status); res.end(status === 204 ? undefined : JSON.stringify(data));
    };
    if (req.method === "GET" && url.pathname === "/faqs") {
      if (cfg.mode === "list-error") { send(500, { detail: "Falha de listagem sintética" }); return; }
      send(200, cfg.mode === "empty" ? [] : faqs); return;
    }
    if (req.method === "POST" && url.pathname === "/faqs") {
      if (cfg.mode === "create-error") { send(500, { detail: "Falha simulada ao criar FAQ." }); return; }
      const created = { ...body, id: `faq-${sequence++}`, created_at: stamp };
      faqs.unshift(created); send(200, created); return;
    }
    const id = url.pathname.split("/")[2];
    const index = faqs.findIndex(faq => faq.id === id);
    if (index === -1) { send(404, { detail: "FAQ sintética não encontrada" }); return; }
    if (req.method === "PUT") {
      if (cfg.mode === "edit-error") { send(500, { detail: "Falha simulada ao editar FAQ. O conteúdo foi preservado para correção." }); return; }
      faqs[index] = { ...faqs[index], ...body }; send(200, faqs[index]); return;
    }
    if (req.method === "DELETE") {
      if (cfg.mode === "delete-error") { send(500, { detail: "Falha simulada ao excluir FAQ." }); return; }
      faqs.splice(index, 1); send(204); return;
    }
    if (req.method === "PATCH" && url.pathname.endsWith("/toggle-chatbot")) {
      if (!faqs[index].show_in_chatbot && faqs.filter(faq => faq.show_in_chatbot).length >= 4) {
        send(409, { detail: "Limite de 4 FAQs no chatbot atingido." }); return;
      }
      faqs[index] = { ...faqs[index], show_in_chatbot: !faqs[index].show_in_chatbot };
      send(200, faqs[index]); return;
    }
  }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Fora da fixture DS-09" }));
}).listen(4131, "127.0.0.1", () => console.log("DS-09 fixture ready at http://127.0.0.1:4131"));

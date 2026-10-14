// DS-08: loopback only, synthetic session/data; never contacts upstream services.
import { createServer } from "node:http";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const directory = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(directory, { recursive: true });
const control = `${directory}/ds08-control.json`;
writeFileSync(control, JSON.stringify({ mode: "ready" }));
const getMode = () => JSON.parse(readFileSync(control, "utf8")).mode;
const user = { id: "00000000-0000-4000-8000-000000000008", email: "ds08@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-12T00:00:00Z" };
const longQuestion = "Como consultar os procedimentos institucionais de matrícula, transferência e bolsas de estudo para o próximo semestre, incluindo prazos, documentos obrigatórios e atendimento aos estudantes de outros campi?";
const dashboard = {
  total_questions: 1234567, unanswered_questions: 12345, avg_response_time: "1,25 s", satisfaction_rate: 92.5,
  daily_interactions: [210, 140, 320, 280, 460, 390, 510].map((count, index) => ({ date: `${index + 6}/10`, count })),
  top_faqs: [longQuestion, "Qual é o horário da biblioteca?", "Como solicitar atendimento acadêmico?", "Onde consultar os documentos institucionais?", "Como localizar os espaços do campus?"].map((question, index) => ({ question, count: 1250 - index * 190 })),
};
const rag = {
  period_days: 30, start_date: "2026-09-13", end_date: "2026-10-12", has_data: true,
  query_count: 1234, query_error_count: 1, failure_count: 3, average_retrieved_results: 2.5, unanswered_rate: 4.25,
  retrieval: { total: 20, success: 19, error: 1, average_latency_ms: 12.5 },
  ingestion: { total: 5, success: 4, error: 1, average_latency_ms: 150.75 },
  source_types: { faq: 8, event: 3, document_chunk: 12, document_parent: 7, other: 0 }, daily: [],
};

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Content-Type", "application/json");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const url = new URL(req.url, "http://127.0.0.1:4121");
  const mode = getMode();
  appendFileSync(`${directory}/ds08-requests.jsonl`, JSON.stringify({ method: req.method, path: url.pathname, query: url.search, mode, authenticated: !!req.headers.authorization }) + "\n");
  if (url.pathname === "/auth/v1/token") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    if (body.email !== user.email || body.password !== "DS08-test-only") { res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant" })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds08-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (url.pathname === "/auth/v1/user") { res.end(JSON.stringify(user)); return; }
  if (url.pathname === "/auth/me") { res.end(JSON.stringify({ ...user, is_active: true })); return; }
  if (url.pathname === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }
  if (url.pathname === "/dashboard") {
    if (mode === "principal-error") { res.writeHead(500); res.end(JSON.stringify({ detail: "erro interno sintético principal" })); return; }
    if (mode === "empty") { res.end(JSON.stringify({ ...dashboard, daily_interactions: [], top_faqs: [] })); return; }
    if (mode === "large") {
      res.end(JSON.stringify({ ...dashboard, total_questions: 9876543210123, unanswered_questions: 1234567890, avg_response_time: "123.456,78 ms", daily_interactions: dashboard.daily_interactions.map(d => ({ ...d, count: d.count * 1234567 })), top_faqs: dashboard.top_faqs.map(d => ({ ...d, count: d.count * 1234567 })) })); return;
    }
    res.end(JSON.stringify(dashboard)); return;
  }
  if (url.pathname === "/dashboard/rag-metrics") {
    if (url.searchParams.get("days") !== "30") { res.writeHead(400); res.end("{}"); return; }
    if (mode === "loading") {
      for (let i = 0; getMode() === "loading" && i < 240; i++) await new Promise(resolve => setTimeout(resolve, 250));
    }
    if (mode === "error") { res.writeHead(500); res.end(JSON.stringify({ detail: "segredo interno sintético do banco" })); return; }
    if (mode === "empty") { res.end(JSON.stringify({ ...rag, has_data: false })); return; }
    if (mode === "large") {
      const scale = value => value * 123456789;
      const operation = op => ({ ...op, total: scale(op.total), success: scale(op.success), error: scale(op.error), average_latency_ms: scale(op.average_latency_ms) });
      res.end(JSON.stringify({ ...rag, query_count: scale(rag.query_count), failure_count: scale(rag.failure_count), average_retrieved_results: scale(rag.average_retrieved_results), retrieval: operation(rag.retrieval), ingestion: operation(rag.ingestion), source_types: Object.fromEntries(Object.entries(rag.source_types).map(([key,value]) => [key, scale(value)])) })); return;
    }
    res.end(JSON.stringify(rag)); return;
  }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Fora da fixture DS-08" }));
}).listen(4121, "127.0.0.1", () => console.log("DS-08 fixture ready at http://127.0.0.1:4121"));

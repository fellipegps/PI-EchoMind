// Local-only fixtures for DS-01 visual verification. Never proxies to real services.
import { createServer } from "node:http";

const user = { id: "00000000-0000-4000-8000-000000000001", email: "ds01@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-11T00:00:00Z" };
const faq = { id: "ds01-faq", question: "Como acessar a biblioteca?", answer: "Consulte os horários na secretaria do campus de teste." };
const metrics = { total_questions: 24, unanswered_questions: 2, avg_response_time: "1,2 s", satisfaction_rate: 92, daily_interactions: [{ date: "10/10", count: 10 }, { date: "11/10", count: 14 }], top_faqs: [{ question: faq.question, count: 8 }] };
const operation = { total: 0, success: 0, error: 0, average_latency_ms: 0 };
const rag = { period_days: 30, start_date: "2026-09-12", end_date: "2026-10-11", has_data: false, query_count: 0, query_error_count: 0, failure_count: 0, average_retrieved_results: 0, unanswered_rate: 0, retrieval: operation, ingestion: operation, source_types: { faq: 0, event: 0, document_chunk: 0, document_parent: 0, other: 0 }, daily: [] };

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Content-Type", "application/json");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const path = new URL(req.url, "http://127.0.0.1:4101").pathname;
  console.log(`${req.method} ${path}`); // No credentials, tokens or request bodies in logs.
  if (path === "/auth/v1/token") {
    let body = "";
    for await (const chunk of req) body += chunk;
    const credentials = JSON.parse(body || "{}");
    if (credentials.email !== user.email || credentials.password !== "DS01-test-only") {
      res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant", error_description: "Credenciais de teste inválidas." })); return;
    }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds01-local-fixture", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (path === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }
  const responses = {
    "/auth/v1/user": user,
    "/auth/me": { id: user.id, email: user.email, is_active: true, created_at: user.created_at },
    "/dashboard": metrics,
    "/dashboard/rag-metrics": rag,
    "/public/ds01-fixture": { public_slug: "ds01-fixture", company_name: "Campus de teste · DS-01", website: null, phone: null, address: null, business_hours: null },
    "/public/ds01-fixture/faqs": [faq],
    "/public/ds01-fixture/events": [],
    "/public/ds01-fixture/locations": [],
  };
  if (path === "/public/ds01-fixture/chat") {
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.end("Resposta **local de teste**."); return;
  }
  if (path in responses) { res.end(JSON.stringify(responses[path])); return; }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Endpoint não definido na fixture DS-01." }));
}).listen(4101, "127.0.0.1", () => console.log("DS-01 fixtures: http://127.0.0.1:4101 (local only)"));

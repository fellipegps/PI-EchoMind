// DS-02: isolated loopback responses. No real account, email, password or upstream service.
// Start with: node test/fixtures/auth-server.mjs
// Preview process only: NEXT_PUBLIC_{API_URL,SUPABASE_URL}=http://127.0.0.1:4103
// NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=ds02-local-fixture-not-a-real-key
import { createServer } from "node:http";

const user = { id: "00000000-0000-4000-8000-000000000002", email: "ds02@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-11T00:00:00Z" };
const failure = "Falha simulada: não foi possível concluir a solicitação. Confira os dados e tente novamente. Esta mensagem extensa serve para verificar a leitura e a quebra de linhas na tela estreita, sem contato com serviços reais.";
const metrics = { total_questions: 0, unanswered_questions: 0, avg_response_time: "0 s", satisfaction_rate: 0, daily_interactions: [], top_faqs: [] };
const operation = { total: 0, success: 0, error: 0, average_latency_ms: 0 };

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Content-Type", "application/json");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const path = new URL(req.url, "http://127.0.0.1:4103").pathname;
  console.log(`${req.method} ${path}`); // Never log request bodies, credentials or tokens.
  let raw = "";
  for await (const chunk of req) raw += chunk;
  const body = JSON.parse(raw || "{}");

  if (req.method === "POST" && ["/auth/v1/token", "/auth/v1/recover", "/auth/v1/signup"].includes(path)) {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    if (body.email === "error@example.test" || (path === "/auth/v1/token" && (body.email !== user.email || body.password !== "DS02-test-only"))) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: "invalid_request", error_description: failure }));
      return;
    }
    if (path === "/auth/v1/recover") { res.end("{}"); return; }
    if (path === "/auth/v1/signup") { res.end(JSON.stringify({ ...user, email: body.email, identities: [] })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds02-local-fixture", token_type: "bearer", expires_in: 3600, expires_at: exp, user }));
    return;
  }
  const responses = {
    "/auth/v1/user": user,
    "/auth/me": { id: user.id, email: user.email, is_active: true, created_at: user.created_at },
    "/dashboard": metrics,
    "/dashboard/rag-metrics": { period_days: 30, start_date: "2026-09-12", end_date: "2026-10-11", has_data: false, query_count: 0, query_error_count: 0, failure_count: 0, average_retrieved_results: 0, unanswered_rate: 0, retrieval: operation, ingestion: operation, source_types: {}, daily: [] },
  };
  if (req.method === "GET" && path in responses) { res.end(JSON.stringify(responses[path])); return; }
  if (path === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }
  res.writeHead(404);
  res.end(JSON.stringify({ detail: "Operação fora da fixture DS-02; nenhuma alteração persistida." }));
}).listen(4103, "127.0.0.1", () => console.log("DS-02 fixtures: http://127.0.0.1:4103 (local only)"));

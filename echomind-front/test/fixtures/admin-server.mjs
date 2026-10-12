// DS-07: isolated loopback fixture; no real account, upstream API or location.
import { createServer } from "node:http";
import { appendFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const logPath = fileURLToPath(new URL("../../.next/ds07-requests.jsonl", import.meta.url));
mkdirSync(fileURLToPath(new URL("../../.next", import.meta.url)), { recursive: true });

const user = { id: "00000000-0000-4000-8000-000000000002", email: "ds07@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-11T00:00:00Z" };
const failure = "Falha simulada: não foi possível concluir a solicitação. Confira os dados e tente novamente. Esta mensagem extensa serve para verificar a leitura e a quebra de linhas na tela estreita, sem contato com serviços reais.";
const metrics = { total_questions: 0, unanswered_questions: 0, avg_response_time: "0 s", satisfaction_rate: 0, daily_interactions: [], top_faqs: [] };
const operation = { total: 0, success: 0, error: 0, average_latency_ms: 0 };

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Content-Type", "application/json");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const fixtureUrl = new URL(req.url, "http://127.0.0.1:4111");
  const path = fixtureUrl.pathname;
  appendFileSync(logPath, JSON.stringify({ method: req.method, path, authenticated: !!req.headers.authorization }) + "\n"); // No tokens or bodies.
  let raw = "";
  for await (const chunk of req) raw += chunk;
  const body = JSON.parse(raw || "{}");

  if (req.method === "POST" && ["/auth/v1/token", "/auth/v1/recover", "/auth/v1/signup"].includes(path)) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    if (body.email === "error@example.test" || (path === "/auth/v1/token" && (![user.email, "rejected@example.test"].includes(body.email) || body.password !== "DS07-test-only"))) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: "invalid_request", error_description: failure }));
      return;
    }
    if (path === "/auth/v1/recover") { res.end("{}"); return; }
    if (path === "/auth/v1/signup") { res.end(JSON.stringify({ ...user, email: body.email, identities: [] })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role, fixture_reject: body.email === "rejected@example.test" })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds07-local-fixture", token_type: "bearer", expires_in: 3600, expires_at: exp, user }));
    return;
  }
  if (path === "/auth/me") {
    const payload = (req.headers.authorization || "").split(".")[1];
    if (!payload || JSON.parse(Buffer.from(payload, "base64url").toString()).fixture_reject) {res.writeHead(401);res.end(JSON.stringify({detail:"Sessão fictícia rejeitada"}));return;}
  }
  const stamp = "2026-10-12T12:00:00Z";
  const responses = {
    "/auth/v1/user": user,
    "/config": { id: "test", public_slug: "ds07-fixture", company_name: "Instituição fictícia · DS-07", description: "Dados de teste para revisão da estrutura administrativa.", tone_of_voice: "profissional e cordial", chat_voice_gender: "feminina", website: null, phone: null, address: null, business_hours: null, updated_at: stamp },
    "/faqs": [{ id: "faq1", question: "Como consultar os espaços e eventos da instituição fictícia? Texto extenso para conferir a tabela.", answer: "Resposta fictícia usada apenas na revisão da estrutura.", show_in_chatbot: true, created_at: stamp }],
    "/documents": { documents: [], total: 0 },
    "/documents/upload-limits": { max_document_size_bytes: 10485760 },
    "/unanswered": [{ id: "question1", canonical_question: "Pergunta fictícia para conferir a rolagem e a estrutura administrativa com uma descrição extensa.", count: 2, first_asked: stamp, last_asked: stamp, similar_questions: [], triage_status: "pending", triage_reason: null }],
    "/events": [{ id: "event1", title: "Encontro fictício de integração e apresentação dos espaços institucionais", event_date: "2026-10-12", event_end_date: "2026-10-13", event_type: "palestra", course: "Curso de teste com nome extenso", description: "Evento fictício", location: "Auditório de teste", image_url: null, link_url: null, created_at: stamp }],
    "/events/courses": [{id:"course",name:"Curso de teste com nome extenso"}],
    "/locations": [{id:"loc1",name:"Laboratório fictício de ensino e pesquisa",description:"Local de teste",category:"laboratório",floor:"1º andar",building:"Bloco fictício",x:40,y:50,active:true,created_at:stamp,updated_at:stamp}],
    "/campuses": [{id:"campus1",name:"Campus fictício · DS-07",description:"Exemplo sintético sem posição real do usuário.",center_lat:-23.5505,center_lng:-46.6333,zoom:17,active:true}],
    "/campuses/campus1/buildings": [{id:"building1",campus_id:"campus1",name:"Bloco de teste",description:"Prédio fictício",category:"ensino",entrance_lat:-23.5505,entrance_lng:-46.6333,entrance_node_id:"node1",active:true}],
    "/campuses/campus1/spaces": [],
    "/campuses/campus1/path-nodes": [{id:"node1",campus_id:"campus1",lat:-23.5505,lng:-46.6333,label:"Entrada de teste"}],
    "/campuses/campus1/path-edges": [],
    "/auth/me": { id: user.id, email: user.email, is_active: true, created_at: user.created_at },
    "/dashboard": metrics,
    "/dashboard/rag-metrics": { period_days: 30, start_date: "2026-09-12", end_date: "2026-10-11", has_data: false, query_count: 0, query_error_count: 0, failure_count: 0, average_retrieved_results: 0, unanswered_rate: 0, retrieval: operation, ingestion: operation, source_types: {}, daily: [] },
  };
  if (path === "/unanswered" && fixtureUrl.searchParams.get("status") !== "pending") {res.end("[]");return;}
  if (req.method === "GET" && path in responses) { res.end(JSON.stringify(responses[path])); return; }
  if (path === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }
  res.writeHead(404);
  res.end(JSON.stringify({ detail: "Operação fora da fixture DS-07; nenhuma alteração persistida." }));
}).listen(4111, "127.0.0.1", () => console.log("DS-07 fixtures: http://127.0.0.1:4111 (local only)"));

// DS-16: synthetic session and in-memory data; loopback only, no upstream services.
import { createServer } from "node:http";
import { appendFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const logPath = fileURLToPath(new URL("../../.next/ds16-requests.jsonl", import.meta.url));
mkdirSync(fileURLToPath(new URL("../../.next/", import.meta.url)), { recursive: true });
const stamp = "2026-10-12T12:00:00Z";
const user = { id: "00000000-0000-4000-8000-000000000016", email: "ds16@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: stamp };
const long = "Referência institucional extensa para conferência de leitura e quebra de linhas: " + "TextoSemEspacos".repeat(12);
let config = { id: "config16", public_slug: "ds16-fixture", company_name: "Instituição sintética de ensino, pesquisa e extensão — DS-16", description: long, tone_of_voice: "profissional e cordial", chat_voice_gender: "feminina", website: "https://example.test", phone: "(00) 00000-0000", address: "Avenida de teste, 1000", business_hours: "Segunda a sexta, das 8h às 22h", updated_at: stamp };
let faqs = [{ id: "faq16", question: "Como consultar os serviços acadêmicos? " + long, answer: "Resposta **de teste** com orientação institucional. " + long, show_in_chatbot: true, created_at: stamp }];
const events = [{ id: "event16", title: "Encontro de integração acadêmica e apresentação dos espaços institucionais", description: long, event_date: "2026-10-20", event_end_date: "2026-10-21", event_type: "palestra", course: "Curso sintético de sistemas de informação", location: "Auditório fictício — Bloco A", image_url: null, link_url: "https://example.test/evento", created_at: stamp }];
const campuses = [{ id: "c1", name: "Campus sintético Central", description: long, center_lat: -23.55045, center_lng: -46.63325, zoom: 18, active: true }];
const nodes = [{ id: "a", campus_id: "c1", lat: -23.5505, lng: -46.6333, label: "Portaria" }, { id: "b", campus_id: "c1", lat: -23.5504, lng: -46.6332, label: "Bloco A" }];
const edges = [{ id: "ab", campus_id: "c1", from_node_id: "a", to_node_id: "b", distance_m: 15.5, accessible: true, active: true }];
const buildings = nodes.map((n, i) => ({ id: `building${i}`, campus_id: "c1", name: n.label, description: "Prédio sintético", category: "ensino", entrance_lat: n.lat, entrance_lng: n.lng, entrance_node_id: n.id, active: true }));
const spaces = [{ id: "space16", campus_id: "c1", building_id: "building1", name: "Laboratório de informática", kind: "laboratório", floor: "1º andar", description: long, active: true }];
const documents = ["ready", "error"].map((status, i) => ({ id: `doc${i}`, filename: i ? "Documento-com-falha.txt" : "Regulamento_institucional_de_matricula_" + "Referencia".repeat(14) + ".pdf", mime_type: i ? "text/plain" : "application/pdf", size_bytes: 1234567, sha256: "a".repeat(64), status, chunk_count: i ? 0 : 1234, document_type: null, document_number: null, department: null, published_at: null, valid_until: null, error_message: i ? "DETALHE_INTERNO_NAO_EXIBIR" : null, created_at: stamp, updated_at: stamp, processed_at: stamp }));
const questions = ["pending", "review", "ignored"].map((status, i) => ({ id: `question${i}`, canonical_question: "Como consultar matrícula e atendimento? " + long, count: i + 12, first_asked: stamp, last_asked: stamp, similar_questions: ["Qual é o prazo acadêmico?"], triage_status: status, triage_reason: i === 1 ? "unclear" : i === 2 ? "ignored_by_admin" : null }));
const dashboard = { total_questions: 1234567, unanswered_questions: 12345, avg_response_time: "1,25 s", satisfaction_rate: 92.5, daily_interactions: [210, 140, 320, 280, 460, 390, 510].map((count, i) => ({ date: `${i + 6}/10`, count })), top_faqs: faqs.map(f => ({ question: f.question, count: 1250 })) };
const rag = { period_days: 30, start_date: "2026-09-13", end_date: "2026-10-12", has_data: true, query_count: 1234, query_error_count: 1, failure_count: 3, average_retrieved_results: 2.5, unanswered_rate: 4.25, retrieval: { total: 20, success: 19, error: 1, average_latency_ms: 12.5 }, ingestion: { total: 5, success: 4, error: 1, average_latency_ms: 150.75 }, source_types: { faq: 8, event: 3, document_chunk: 12, document_parent: 7, other: 0 }, daily: [] };
let sequence = 0;

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const url = new URL(req.url, "http://127.0.0.1:4201");
  const path = url.pathname;
  let raw = ""; for await (const chunk of req) raw += chunk;
  const body = raw ? JSON.parse(raw) : {};
  const record = { id: ++sequence, method: req.method, path, query: url.search, authenticated: !!req.headers.authorization };
  const log = value => appendFileSync(logPath, JSON.stringify(value) + "\n");
  const send = (status, data) => { log({ ...record, status, ...(req.method !== "GET" && !path.startsWith("/auth/") ? { payload: body } : {}) }); res.writeHead(status); res.end(status === 204 ? undefined : JSON.stringify(data)); };
  if (path === "/auth/v1/token") {
    if (body.email !== user.email || body.password !== "DS16-test-only") { send(400, { error: "invalid_grant" }); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    send(200, { access_token: jwt, refresh_token: "ds16-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user }); return;
  }
  if (["/auth/v1/signup", "/auth/v1/recover"].includes(path)) { send(200, path.endsWith("signup") ? { ...user, email: body.email, identities: [] } : {}); return; }
  if (["/auth/v1/user", "/auth/me"].includes(path)) { send(200, { ...user, is_active: true }); return; }
  if (path === "/auth/v1/logout") { send(204); return; }
  // Public requests never require or forward a real session.
  const publicMatch = path.match(/^\/public\/(ds16-fixture|ds16-empty|ds16-error)(\/.*)?$/);
  if (path === "/chat" || publicMatch?.[2] === "/chat") {
    if (path === "/chat" && body.tenant_id !== user.id) { send(400, { detail: "Contexto fictício incorreto" }); return; }
    res.setHeader("Content-Type", "text/plain; charset=utf-8"); res.flushHeaders();
    log({ ...record, status: 200, payload: body, stage: "stream-start" });
    await new Promise(resolve => setTimeout(resolve, 700)); res.write("Resposta **sintética**: ");
    await new Promise(resolve => setTimeout(resolve, 700)); res.end(long + "\n\n- Orientação institucional de teste.\n<img src=x onerror=alert(1)>");
    log({ ...record, status: 200, stage: "stream-done" }); return;
  }
  if (publicMatch) {
    const suffix = publicMatch[2] || "";
    if (publicMatch[1] === "ds16-error" && suffix === "/geo-campus") { send(500, { detail: "DETALHE_INTERNO_SINTETICO" }); return; }
    const geo = publicMatch[1] === "ds16-empty" ? { campuses: [], buildings: [], spaces: [], nodes: [], edges: [] } : { campuses, buildings, spaces, nodes, edges };
    const data = { "": config, "/faqs": faqs.filter(f => f.show_in_chatbot), "/events": events, "/geo-campus": geo };
    if (suffix in data) { send(200, data[suffix]); return; }
  }
  // Tiny local tile: no calls to OSM/MapTiler, attribution stays explicit.
  if (path.startsWith("/tiles/")) { res.setHeader("Content-Type", "image/png"); log({ ...record, status: 200 }); res.end(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1EAAAAASUVORK5CYII=", "base64")); return; }
  if (!req.headers.authorization) { send(401, { detail: "Sessão fictícia necessária" }); return; }
  if (path === "/config" && req.method === "PUT") { config = { ...config, ...body, updated_at: stamp }; send(200, config); return; }
  if (path === "/faqs" && req.method === "POST") { const faq = { id: `faq${sequence}`, ...body, created_at: stamp }; faqs.push(faq); send(200, faq); return; }
  const faqMatch = path.match(/^\/faqs\/([^/]+)$/);
  if (faqMatch && req.method === "PUT") { const faq = faqs.find(f => f.id === faqMatch[1]); Object.assign(faq, body); send(200, faq); return; }
  if (faqMatch && req.method === "DELETE") { faqs = faqs.filter(f => f.id !== faqMatch[1]); send(204); return; }
  if (req.method !== "GET") { send(404, { detail: "Operação não implementada na fixture; nada persistido" }); return; }
  const responses = { "/config": config, "/dashboard": dashboard, "/dashboard/rag-metrics": rag, "/faqs": faqs, "/documents": { documents, total: documents.length }, "/documents/upload-limits": { max_document_size_bytes: 10485760 }, "/unanswered": questions.filter(q => q.triage_status === (url.searchParams.get("status") || "pending")), "/events": events, "/events/courses": [{ id: "course16", name: events[0].course }], "/campuses": campuses, "/campuses/c1/buildings": buildings, "/campuses/c1/spaces": spaces, "/campuses/c1/path-nodes": nodes, "/campuses/c1/path-edges": edges };
  if (path in responses) { send(200, responses[path]); return; }
  send(404, { detail: "Fora da fixture DS-16" });
}).listen(4201, "127.0.0.1", () => console.log("DS-16 fixture ready at http://127.0.0.1:4201"));

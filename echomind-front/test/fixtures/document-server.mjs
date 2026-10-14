// DS-10: loopback synthetic API; files and data are disposable, in memory, no upstream.
import { createServer } from "node:http";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const dir = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(dir, { recursive: true });
const control = `${dir}/ds10-control.json`;
writeFileSync(control, JSON.stringify({ mode: "ready", hold: null, revision: 0 }));
const config = () => JSON.parse(readFileSync(control, "utf8"));
const user = { id: "00000000-0000-4000-8000-000000000010", email: "ds10@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-12T00:00:00Z" };
const stamp = "2026-10-12T12:00:00Z";
const longName = "Regulamento_institucional_de_matricula_transferencia_bolsas_e_atendimento_aos_estudantes_" + "ReferenciaInstitucional".repeat(4) + ".pdf";
const initial = () => ["pending", "processing", "ready", "error"].map((status, i) => ({ id: `doc-${i+1}`, filename: i === 2 ? longName : `${status}-sintetico.txt`, mime_type: i === 2 ? "application/pdf" : "text/plain", size_bytes: i === 2 ? 1234567 : 2048, sha256: "a".repeat(64), status, chunk_count: i === 2 ? 12345 : 0, document_type: null, document_number: null, department: null, published_at: null, valid_until: null, error_message: status === "error" ? "SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR" : null, created_at: stamp, updated_at: stamp, processed_at: status === "ready" || status === "error" ? stamp : null }));
let documents = initial();
let revision = 0;
let nextId = 5;
let activeLists = 0;
let sequence = 0;
let progressReads = 0;
createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS");
  res.setHeader("Content-Type", "application/json");
  if (req.method === "OPTIONS") { res.writeHead(204);res.end();return; }
  const url = new URL(req.url, "http://127.0.0.1:4141");
  let cfg = config();
  if (revision !== cfg.revision) { revision = cfg.revision; documents = initial(); nextId = 5; progressReads = 0; }
  const id = ++sequence;
  const record = { id, method: req.method, path: url.pathname, mode: cfg.mode, hold: cfg.hold, authenticated: !!req.headers.authorization, startedAt: Date.now() };
  const log = entry => appendFileSync(`${dir}/ds10-requests.jsonl`, JSON.stringify(entry) + "\n");
  log(record);
  if (url.pathname === "/auth/v1/token") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    if (body.email !== user.email || body.password !== "DS10-test-only") { res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant" })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds10-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (url.pathname === "/auth/v1/user") { res.end(JSON.stringify(user)); return; }
  if (url.pathname === "/auth/me") { res.end(JSON.stringify({ ...user, is_active: true })); return; }
  if (url.pathname === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }


  if (url.pathname === "/dashboard") { res.end(JSON.stringify({ total_questions:0,unanswered_questions:0,avg_response_time:"0 s",satisfaction_rate:0,daily_interactions:[],top_faqs:[] }));return; }
  if (url.pathname === "/dashboard/rag-metrics") {res.end(JSON.stringify({has_data:false}));return;}
  if (url.pathname === "/faqs") { res.end("[]");return; }
  const operation = url.pathname === "/documents/upload-limits" ? "limits" : req.method === "GET" ? "list" : req.method === "POST" ? "upload" : "delete";
  if (url.pathname.startsWith("/documents")) {
    if (operation === "list") { activeLists++; log({ id, event:"list-start", activeLists, at:Date.now() }); }
    let raw = [];
    for await (const chunk of req) raw.push(chunk);
    const buffer = Buffer.concat(raw);
    for (let i=0; config().hold === operation && i<2400; i++) await new Promise(resolve=>setTimeout(resolve,250));
    cfg = config();
    const send = (status, data, extra={}) => {
      if (operation === "list") activeLists--;
      log({ ...record, completed:true, status, endedAt:Date.now(), ...(operation === "list" ? {activeLists} : {}), ...extra });
      res.writeHead(status);res.end(status===204?undefined:JSON.stringify(data));
    };
    if (operation === "limits") {
      if (cfg.mode === "limit-error") {send(500,{detail:"SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR"});return;}
      send(200,{max_document_size_bytes:cfg.mode === "limit-invalid" ? 0 : 2*1024*1024});return;
    }
    if (operation === "list") {
      if (["list-error","poll-error"].includes(cfg.mode)) {send(500,{detail:"SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR"});return;}
      if (cfg.mode === "progress") {
        progressReads++;
        documents = [ {...initial()[0], status:progressReads===1?"pending":progressReads===2?"processing":"ready", chunk_count:progressReads>=3?7:0} ];
      }
      if (cfg.mode === "final") documents = documents.map(d=>["pending","processing"].includes(d.status)?{...d,status:"ready",chunk_count:7}:d);
      send(200,{documents:cfg.mode==="empty"?[]:documents,total:cfg.mode==="empty"?0:documents.length});return;
    }
    if (operation === "upload" && url.pathname === "/documents/upload") {
      const form = await new Request("http://127.0.0.1:4141/documents", {method:"POST",headers:{"Content-Type":req.headers["content-type"]},body:buffer}).formData();
      const file = form.get("file");
      const metadata = Object.fromEntries([...form.entries()].filter(([key])=>key!=="file"));
      if (cfg.mode === "upload-error") {send(500,{detail:"SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR"},{file:{name:file.name,size:file.size,type:file.type},metadata});return;}
      const created = {...initial()[0],id:`doc-${nextId++}`,filename:file.name,mime_type:file.type,size_bytes:file.size,...metadata};
      documents.unshift(created);send(200,created,{file:{name:file.name,size:file.size,type:file.type},metadata});return;
    }
    if (operation === "delete") {
      if (cfg.mode === "delete-error") {send(500,{detail:"SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR"});return;}
      const index = documents.findIndex(d=>d.id===url.pathname.split("/")[2]);
      if (index<0) {send(404,{detail:"Documento sintético ausente"});return;}
      if (["pending","processing"].includes(documents[index].status)) {send(409,{detail:"Documento ativo"});return;}
      documents.splice(index,1);send(204);return;
    }
    send(404,{detail:"Operação fora da fixture DS-10"});return;
  }
  res.writeHead(404);res.end(JSON.stringify({detail:"Fora da fixture DS-10"}));
}).listen(4141,"127.0.0.1",()=>console.log("DS-10 fixture ready at http://127.0.0.1:4141"));

// DS-03: isolated public-portal fixtures. No upstream calls or real institutional data.
import { createServer } from "node:http";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// Keep ongoing review traffic out of the frozen evidence snapshot.
const logPath = fileURLToPath(new URL("../../.next/ds03-requests.jsonl", import.meta.url));
mkdirSync(dirname(logPath), { recursive: true });
const counts = new Map();
const faqs = Array.from({ length: 4 }, (_, index) => ({ id: `ds03-faq-${index + 1}`, question: ["Como acessar a biblioteca?", "Onde encontro os horários de atendimento?", "Como consultar os eventos do campus?", "Como encontrar um local no campus?"][index], answer: "Resposta local de teste." }));
const events = Array.from({ length: 12 }, (_, index) => ({ id: `ds03-event-${index + 1}`, title: `Evento de teste ${index + 1}`, event_date: "2099-10-20", event_end_date: "2099-10-21", event_type: "evento_social", course: "Curso de teste", description: "Atividade fictícia para verificar a rolagem e a navegação do portal.", location: "Auditório de teste", image_url: null, link_url: "http://127.0.0.1:4104/info/evento" }));

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const path = new URL(req.url, "http://127.0.0.1:4104").pathname;
  const key = `${req.method} ${path}`;
  counts.set(key, (counts.get(key) ?? 0) + 1);
  appendFileSync(logPath, JSON.stringify({ request: key, count: counts.get(key) }) + "\n");
  console.log(key); // No bodies, credentials or tokens.
  if (path === "/info/evento") { res.end(JSON.stringify({ title: "Evento local de teste" })); return; }
  const match = path.match(/^\/public\/(ds03-fixture|ds03-longo)(\/[^?]*)?$/);
  if (!match) { res.writeHead(404); res.end(JSON.stringify({ detail: "Instituição de teste não encontrada." })); return; }
  const [, slug, suffix = ""] = match;
  if (suffix === "/chat") {
    for await (const chunk of req) { void chunk; }
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.flushHeaders();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    res.write("Resposta **local** ");
    await new Promise((resolve) => setTimeout(resolve, 6500));
    res.end("preservada após a navegação e a troca de largura.");
    return;
  }
  const responses = {
    "": { public_slug: slug, company_name: slug === "ds03-longo" ? "Instituição de Ensino Superior de Teste com Nome Extenso para Verificar a Leitura e a Navegação do Portal em Todas as Larguras" : "Campus de teste · DS-03", website: null, phone: null, address: null, business_hours: null },
    "/faqs": faqs,
    "/events": events,
    "/geo-campus": { campuses: [], buildings: [], spaces: [], nodes: [], edges: [] },
  };
  if (suffix in responses) { res.end(JSON.stringify(responses[suffix])); return; }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Operação não definida na fixture DS-03." }));
}).listen(4104, "127.0.0.1", () => console.log("DS-03 fixtures: http://127.0.0.1:4104 (local only)"));

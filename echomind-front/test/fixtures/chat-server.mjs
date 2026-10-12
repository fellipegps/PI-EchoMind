// DS-04: isolated public-portal fixtures. No upstream calls or real institutional data.
import { createServer } from "node:http";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// Keep ongoing review traffic out of the frozen evidence snapshot.
const logPath = fileURLToPath(new URL("../../.next/ds04-requests.jsonl", import.meta.url));
mkdirSync(dirname(logPath), { recursive: true });
const counts = new Map();
const faqs = Array.from({ length: 4 }, (_, index) => ({ id: `ds04-faq-${index + 1}`, question: ["Como acessar a biblioteca?", "Onde encontro os horários de atendimento?", "Como consultar os eventos do campus?", "Como encontrar um local no campus?"][index], answer: "Resposta local de teste." }));
const events = Array.from({ length: 3 }, (_, index) => ({ id: `ds04-event-${index + 1}`, title: `Evento de teste ${index + 1}`, event_date: "2099-10-20", event_end_date: "2099-10-21", event_type: "evento_social", course: "Curso de teste", description: "Atividade fictícia para verificar a rolagem e a navegação do portal.", location: "Auditório de teste", image_url: null, link_url: "http://127.0.0.1:4105/info/evento" }));
const locations = Array.from({ length: 12 }, (_, index) => ({ id: `ds04-local-${index + 1}`, name: `Local de teste ${index + 1}`, description: "Local fictício para inspecionar a estrutura.", category: "ensino", floor: "Térreo", building: "Bloco de teste", x: 20 + (index % 4) * 20, y: 20 + Math.floor(index / 4) * 25 }));

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const path = new URL(req.url, "http://127.0.0.1:4105").pathname;
  const key = `${req.method} ${path}`;
  counts.set(key, (counts.get(key) ?? 0) + 1);
  appendFileSync(logPath, JSON.stringify({ request: key, count: counts.get(key) }) + "\n");
  console.log(key); // No bodies, credentials or tokens.
  if (path === "/info/evento") { res.end(JSON.stringify({ title: "Evento local de teste" })); return; }
  const match = path.match(/^\/public\/(ds04-fixture|ds04-longo|ds04-loading)(\/[^?]*)?$/);
  if (!match) { res.writeHead(404); res.end(JSON.stringify({ detail: "Instituição de teste não encontrada." })); return; }
  const [, slug, suffix = ""] = match;
  if (suffix === "/chat") {
    let body = "";
    for await (const chunk of req) body += chunk;
    const { message: question } = JSON.parse(body);
    // Only synthetic local questions; never forward to a model or service.
    appendFileSync(logPath, JSON.stringify({ slug, question }) + "\n");
    if (question.includes("falha")) {
      res.writeHead(500); res.end(JSON.stringify({ detail: "detalhe interno da fixture" })); return;
    }
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.flushHeaders();
    await new Promise((resolve) => setTimeout(resolve, 6000));
    res.write("Resposta **lo");
    await new Promise((resolve) => setTimeout(resolve, 2500));
    const long = question.includes("longa") ? "\n\n" + Array.from({ length: 10 }, (_, index) => `Parágrafo ${index + 1}: Conteúdo local extenso para conferir leitura, rolagem e envio após a resposta. `).join("\n\n") + "\n\n- Item permitido\n- Segundo item\n\n[https://example.com/" + "caminho".repeat(35) + "](https://example.com/" + "caminho".repeat(35) + ")\n\n```js\nconst exemplo = '" + "codigo".repeat(90) + "';\n```\n\n[Link inseguro](javascript:alert%281%29) <script>alert('teste')</script>" : "";
    res.end("cal** preservada após a navegação e a troca de largura." + long);
    return;
  }
  if (slug === "ds04-loading" && suffix === "") await new Promise((resolve) => setTimeout(resolve, 6000));
  const responses = {
    "": { public_slug: slug, company_name: slug === "ds04-longo" ? "Instituição de Ensino Superior de Teste com Nome Extenso para Verificar a Leitura e a Navegação do Portal em Todas as Larguras" : "Campus de teste · DS-04", website: null, phone: null, address: null, business_hours: null },
    "/faqs": faqs,
    "/events": events,
    "/locations": locations,
    "/geo-campus": { campuses: [], buildings: [], spaces: [], nodes: [], edges: [] },
  };
  if (suffix in responses) { res.end(JSON.stringify(responses[suffix])); return; }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Operação não definida na fixture DS-04." }));
}).listen(4105, "127.0.0.1", () => console.log("DS-04 fixtures: http://127.0.0.1:4105 (local only)"));

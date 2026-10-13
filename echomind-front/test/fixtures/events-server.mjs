// DS-05: isolated public-portal fixtures. No upstream calls or real institutional data.
import { createServer } from "node:http";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// Keep ongoing review traffic out of the frozen evidence snapshot.
const logPath = fileURLToPath(new URL("../../.next/ds05-requests.jsonl", import.meta.url));
mkdirSync(dirname(logPath), { recursive: true });
const counts = new Map();
const faqs = Array.from({ length: 4 }, (_, index) => ({ id: `ds05-faq-${index + 1}`, question: ["Como acessar a biblioteca?", "Onde encontro os horários de atendimento?", "Como consultar os eventos do campus?", "Como encontrar um local no campus?"][index], answer: "Resposta local de teste." }));
const events = [
  { id: "ds05-event-1", title: "Semana de projetos acadêmicos · evento de teste", event_date: "2099-08-15", event_end_date: "2099-08-15", event_type: "evento_social", course: "Engenharia de Software · Curso de teste", description: "Exposição fictícia dos projetos desenvolvidos pelos estudantes.\nTodos os detalhes recebidos permanecem disponíveis na agenda.", location: "Auditório Central · Campus de teste", image_url: "https://placehold.co/1200x675/png?text=Capa+de+teste", link_url: "http://127.0.0.1:4107/info/evento-1" },
  { id: "ds05-event-2", title: "Encontro de pesquisa · capa vertical de teste", event_date: "2099-08-15", event_end_date: "2099-08-17", event_type: "evento_social", course: "Ciências Biológicas · Curso de teste", description: "Apresentação fictícia de trabalhos de pesquisa com uma capa de proporção vertical.", location: "Laboratório de teste", image_url: "https://placehold.co/300x600/png?text=Capa+vertical", link_url: "http://127.0.0.1:4107/info/evento-2" },
  { id: "ds05-event-3", title: "Jornada institucional sem capa e com título extenso para conferir a leitura completa em todas as larguras · " + "TextoExtenso".repeat(8), event_date: "2099-08-31", event_end_date: "2099-09-02", event_type: "evento_social", course: "Curso institucional de teste com nome extenso para verificar a apresentação dos metadados", description: "Descrição fictícia extensa. ".repeat(18), location: "Espaço de teste com identificação longa e acesso pelo bloco acadêmico", image_url: null, link_url: "http://127.0.0.1:4107/info/" + "enderecoextenso".repeat(15) },
  { id: "ds05-event-4", title: "Virada acadêmica · capa quebrada de teste", event_date: "2099-12-31", event_end_date: "2100-01-02", event_type: "evento_social", course: "Administração · Curso de teste", description: "A capa deve falhar sem retirar este texto, os metadados ou o link.", location: "Sala de teste", image_url: "https://placehold.co/ds05-inexistente.png", link_url: "http://127.0.0.1:4107/info/evento-4" },
  { id: "ds05-event-5", title: "Encontro com campos opcionais ausentes", event_date: "2100-01-03", event_end_date: "2100-01-03", event_type: "evento_social", course: "Curso de teste", description: null, location: "Sala de teste", image_url: "http://example.com/capa-nao-permitida.png", link_url: "javascript:alert(1)" },
];

createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
  const path = new URL(req.url, "http://127.0.0.1:4107").pathname;
  const key = `${req.method} ${path}`;
  counts.set(key, (counts.get(key) ?? 0) + 1);
  appendFileSync(logPath, JSON.stringify({ request: key, count: counts.get(key) }) + "\n");
  console.log(key); // No bodies, credentials or tokens.
  if (path.startsWith("/info/")) { res.end(JSON.stringify({ title: "Evento local de teste" })); return; }
  const match = path.match(/^\/public\/(ds05-fixture|ds05-alternate|ds05-empty|ds05-error|ds05-loading)(\/[^?]*)?$/);
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
  if (suffix === "/events" && slug === "ds05-loading") await new Promise((resolve) => setTimeout(resolve, 6000));
  if (suffix === "/events" && slug === "ds05-error") { res.writeHead(500); res.end(JSON.stringify({ detail: "detalhe interno da fixture" })); return; }
  const responses = {
    "": { public_slug: slug, company_name: slug === "ds05-alternate" ? "Outra instituição · DS-05" : "Campus de teste · DS-05", website: null, phone: null, address: null, business_hours: null },
    "/faqs": faqs,
    "/events": slug === "ds05-empty" ? [] : slug === "ds05-alternate" ? [{ ...events[0], id: "ds05-other", title: "Evento exclusivo da segunda instituição" }] : events,
    "/geo-campus": { campuses: [], buildings: [], spaces: [], nodes: [], edges: [] },
  };
  if (suffix in responses) { res.end(JSON.stringify(responses[suffix])); return; }
  res.writeHead(404); res.end(JSON.stringify({ detail: "Operação não definida na fixture DS-05." }));
}).listen(4107, "127.0.0.1", () => console.log("DS-05 fixtures: http://127.0.0.1:4107 (local only)"));

// DS-11: disposable synthetic triage/FAQ data on loopback; no upstream requests.
import { createServer } from "node:http";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const directory = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(directory, { recursive: true });
const control = `${directory}/ds11-control.json`;
writeFileSync(control, JSON.stringify({ mode: "ready", hold: null, revision: 0 }));
const config = () => JSON.parse(readFileSync(control, "utf8"));
const user = { id: "00000000-0000-4000-8000-000000000011", email: "ds11@example.test", aud: "authenticated", role: "authenticated", app_metadata: {}, user_metadata: {}, created_at: "2026-10-12T00:00:00Z" };
const stamp = "2026-10-12T12:00:00Z";
const longQuestion = "Como consultar os procedimentos de MATRÍCULA, transferência, bolsas e atendimento aos estudantes de outros campi? Referência extensa: " + "ReferenciaInstitucional".repeat(9);
const initial = () => [
  { id:"pending-1",canonical_question:longQuestion,count:12345,first_asked:"2026-09-01T12:00:00Z",last_asked:stamp,similar_questions:["Onde consultar o HISTÓRICO ACADÊMICO?", "Como acompanhar a matrícula e os documentos necessários? " + "VariacaoSemEspacos".repeat(9)],triage_status:"pending",triage_reason:null },
  { id:"pending-2",canonical_question:"Qual é o horário da biblioteca?",count:1,first_asked:stamp,last_asked:stamp,similar_questions:[],triage_status:"pending",triage_reason:null },
  ...["abusive_language","possible_off_topic","external_link","unclear","mixed_variants","unknown_reason"].map((reason,i)=>({id:`review-${i+1}`,canonical_question:i===0?"Como revisar uma pergunta extensa antes de criar conhecimento? "+"PerguntaEmRevisao".repeat(8):`Pergunta sintética para revisar: ${reason}`,count:i+2,first_asked:stamp,last_asked:stamp,similar_questions:["Variação sintética em revisão."],triage_status:"review",triage_reason:reason})),
  ...["ignored_by_admin","no_usable_question"].map((reason,i)=>({id:`ignored-${i+1}`,canonical_question:i===0?"Pergunta ignorada pelo administrador: "+"TextoIgnorado".repeat(8):"Mensagem filtrada sem pergunta aproveitável",count:3,first_asked:stamp,last_asked:stamp,similar_questions:["Repetição sintética ignorada."],triage_status:"ignored",triage_reason:reason}))
];
let questions = initial();let faqs=[];let revision=0;let sequence=0;
createServer(async(req,res)=>{
  res.setHeader("Access-Control-Allow-Origin","*");res.setHeader("Access-Control-Allow-Headers","*");res.setHeader("Access-Control-Allow-Methods","GET,POST,OPTIONS");res.setHeader("Content-Type","application/json");
  if(req.method==="OPTIONS"){res.writeHead(204);res.end();return;}
  const url=new URL(req.url,"http://127.0.0.1:4151");let cfg=config();
  if(cfg.revision!==revision){questions=initial();faqs=[];revision=cfg.revision;}
  const record={id:++sequence,method:req.method,path:url.pathname,query:url.search,mode:cfg.mode,hold:cfg.hold,authenticated:!!req.headers.authorization,startedAt:Date.now()};
  const log=entry=>appendFileSync(`${directory}/ds11-requests.jsonl`,JSON.stringify(entry)+"\n");log(record);
  if (url.pathname === "/auth/v1/token") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    if (body.email !== user.email || body.password !== "DS11-test-only") { res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant" })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds11-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (url.pathname === "/auth/v1/user") { res.end(JSON.stringify(user)); return; }
  if (url.pathname === "/auth/me") { res.end(JSON.stringify({ ...user, is_active: true })); return; }
  if (url.pathname === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }


  if(url.pathname==="/dashboard"){res.end(JSON.stringify({total_questions:0,unanswered_questions:0,avg_response_time:"0 s",satisfaction_rate:0,daily_interactions:[],top_faqs:[]}));return;}
  if(url.pathname==="/dashboard/rag-metrics"){res.end(JSON.stringify({has_data:false}));return;}
  if(url.pathname==="/faqs"){res.end(JSON.stringify(faqs));return;}
  if(url.pathname.startsWith("/unanswered")){
    let raw="";for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw||"{}");
    const operation=req.method==="GET"?"list":url.pathname.split("/").at(-1);
    for(let i=0;config().hold===operation&&i<2400;i++)await new Promise(resolve=>setTimeout(resolve,250));cfg=config();
    const send=(status,data)=>{log({...record,completed:true,status,endedAt:Date.now(),...(operation==="convert"?{payload:body}:{})});res.writeHead(status);res.end(status===204?undefined:JSON.stringify(data));};
    if(cfg.mode===`${operation}-error`){send(500,{detail:"SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR"});return;}
    if(operation==="list"){send(200,cfg.mode==="empty"?[]:questions.filter(q=>q.triage_status===url.searchParams.get("status")));return;}
    const index=questions.findIndex(q=>q.id===url.pathname.split("/")[2]);if(index<0){send(404,{detail:"Pergunta sintética ausente"});return;}
    if(operation==="convert"){
      const faq={id:`faq-${record.id}`,question:body.question,answer:body.answer,show_in_chatbot:false,created_at:stamp};faqs.unshift(faq);questions.splice(index,1);send(200,faq);return;
    }
    if(operation==="ignore"){questions[index]={...questions[index],triage_status:"ignored",triage_reason:"ignored_by_admin"};send(204);return;}
    if(operation==="approve"||operation==="restore"){questions[index]={...questions[index],triage_status:"pending",triage_reason:operation==="restore"?"approved_by_admin":null};send(204);return;}
    send(404,{detail:"Operação fora da fixture DS-11"});return;
  }
  res.writeHead(404);res.end(JSON.stringify({detail:"Fora da fixture DS-11"}));
}).listen(4151,"127.0.0.1",()=>console.log("DS-11 fixture ready at http://127.0.0.1:4151"));

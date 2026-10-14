// DS-12: disposable events/courses and authentication on loopback; no upstream.
import { createServer } from "node:http";
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const directory = fileURLToPath(new URL("../../.next/", import.meta.url));
mkdirSync(directory, { recursive: true });
const control = `${directory}/ds12-control.json`;
writeFileSync(control, JSON.stringify({mode:"ready",hold:null,revision:0}));
const config=()=>JSON.parse(readFileSync(control,"utf8"));
const user={id:"00000000-0000-4000-8000-000000000012",email:"ds12@example.test",aud:"authenticated",role:"authenticated",app_metadata:{},user_metadata:{},created_at:"2026-10-12T00:00:00Z"};
const longCourse="Curso institucional de referência: "+"CursoExtenso".repeat(12);
const initial=()=>[
 {id:"event-later",title:"Jornada de encerramento anual: "+"TituloSemEspacos".repeat(12),event_date:"2026-12-31",event_end_date:"2027-01-02",event_type:"evento_social",course:longCourse,description:"Descrição sintética extensa. ".repeat(30),location:"Local de referência "+"LocalSemEspacos".repeat(12),image_url:null,link_url:"http://127.0.0.1:4161/info/jornada",created_at:"2026-10-12T12:00:00Z"},
 {id:"event-beta",title:"Beta · Semana de Computação",event_date:"2026-10-15",event_end_date:"2026-10-17",event_type:"workshop",course:"Computação",description:"Descrição sintética de três dias.",location:"Laboratório de teste",image_url:null,link_url:null,created_at:"2026-10-12T12:00:00Z"},
 {id:"event-alpha",title:"Alpha · Encontro de um dia",event_date:"2026-10-15",event_end_date:"2026-10-15",event_type:"palestra",course:"Geral",description:null,location:"Auditório de teste",image_url:null,link_url:null,created_at:"2026-10-12T12:00:00Z"}
];
const initialCourses=()=>[{id:"general",name:"Geral"},{id:"computing",name:"Computação"},{id:"long",name:longCourse}];
let events=initial(),courses=initialCourses(),revision=0,sequence=0;
createServer(async(req,res)=>{
 res.setHeader("Access-Control-Allow-Origin","*");res.setHeader("Access-Control-Allow-Headers","*");res.setHeader("Access-Control-Allow-Methods","GET,POST,PUT,DELETE,OPTIONS");res.setHeader("Content-Type","application/json; charset=utf-8");
 if(req.method==="OPTIONS"){res.writeHead(204);res.end();return;}
 const url=new URL(req.url,"http://127.0.0.1:4161");let cfg=config();
 if(cfg.revision!==revision){events=initial();courses=initialCourses();revision=cfg.revision;}
 const record={id:++sequence,method:req.method,path:url.pathname,mode:cfg.mode,hold:cfg.hold,authenticated:!!req.headers.authorization,startedAt:Date.now()};
 const log=x=>appendFileSync(`${directory}/ds12-requests.jsonl`,JSON.stringify(x)+"\n");log(record);
  if (url.pathname === "/auth/v1/token") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    const body = JSON.parse(raw || "{}");
    if (body.email !== user.email || body.password !== "DS12-test-only") { res.writeHead(400); res.end(JSON.stringify({ error: "invalid_grant" })); return; }
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const jwt = [Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"), Buffer.from(JSON.stringify({ sub: user.id, exp, role: user.role })).toString("base64url"), "local-fixture-only"].join(".");
    res.end(JSON.stringify({ access_token: jwt, refresh_token: "ds12-fixture-only", token_type: "bearer", expires_in: 3600, expires_at: exp, user })); return;
  }
  if (url.pathname === "/auth/v1/user") { res.end(JSON.stringify(user)); return; }
  if (url.pathname === "/auth/me") { res.end(JSON.stringify({ ...user, is_active: true })); return; }
  if (url.pathname === "/auth/v1/logout") { res.writeHead(204); res.end(); return; }



 if(url.pathname==="/dashboard"){res.end(JSON.stringify({total_questions:0,unanswered_questions:0,avg_response_time:"0 s",satisfaction_rate:0,daily_interactions:[],top_faqs:[]}));return;}
 if(url.pathname==="/dashboard/rag-metrics"){res.end(JSON.stringify({has_data:false}));return;}
 if(url.pathname.startsWith("/info/")){res.end(JSON.stringify({message:"Destino sintético"}));return;}
 if(url.pathname.startsWith("/events")){
  let raw="";for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw||"{}");
  const isCourse=url.pathname==="/events/courses";
  const operation=req.method==="GET"?"list":isCourse?"course":req.method==="POST"?"create":req.method==="PUT"?"update":"delete";
  for(let i=0;config().hold===operation&&i<2400;i++)await new Promise(resolve=>setTimeout(resolve,250));cfg=config();
  const send=(status,data)=>{log({...record,completed:true,status,endedAt:Date.now(),...(req.method!=="GET"?{payload:body}:{})});res.writeHead(status);res.end(status===204?undefined:JSON.stringify(data));};
  if(cfg.mode===`${operation}-error`){send(500,{detail:"SEGREDO_INTERNO_SINTETICO_NAO_EXIBIR"});return;}
  if(operation==="list"){send(200,isCourse?courses:cfg.mode==="empty"?[]:events);return;}
  if(operation==="course"){const created={id:`course-${sequence}`,name:body.name};courses.push(created);send(201,created);return;}
  if(operation==="create"){const created={...body,id:`event-created-${sequence}`,created_at:"2026-10-12T12:00:00Z"};events.push(created);send(201,created);return;}
  const index=events.findIndex(x=>x.id===url.pathname.split("/")[2]);if(index<0){send(404,{detail:"Evento sintético ausente"});return;}
  if(operation==="update"){events[index]={...events[index],...body};send(200,events[index]);return;}
  if(operation==="delete"){events.splice(index,1);send(204);return;}
 }
 res.writeHead(404);res.end(JSON.stringify({detail:"Fora da fixture DS-12"}));
}).listen(4161,"127.0.0.1",()=>console.log("DS-12 fixture ready at http://127.0.0.1:4161"));

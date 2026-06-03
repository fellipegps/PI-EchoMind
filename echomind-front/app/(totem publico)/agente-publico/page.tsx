"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Mic, ChevronRight, X, Volume2, VolumeX, Send, ThumbsUp, ThumbsDown, Keyboard } from "lucide-react";
import { streamChat, faqApi, configApi, feedbackApi } from "@/lib/api";
import type { Faq } from "@/lib/api";

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

type ListeningState = "idle" | "listening" | "processing" | "responding";

const BAR_COUNT = 12;

// ─── Hook: Speech Recognition ─────────────────────────────────────────────────

function useSpeechRecognition() {
  const [state, setState]           = useState<ListeningState>("idle");
  const [transcript, setTranscript] = useState("");
  const [barHeights, setBarHeights] = useState<number[]>(Array(BAR_COUNT).fill(8));
  const recognitionRef = useRef<any>(null);
  const barAnimRef     = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopBarAnimation = useCallback(() => {
    if (barAnimRef.current) clearInterval(barAnimRef.current);
    setBarHeights(Array(BAR_COUNT).fill(4));
  }, []);

  const startBarAnimation = useCallback(() => {
    barAnimRef.current = setInterval(() => {
      setBarHeights(Array.from({ length: BAR_COUNT }, () => 6 + Math.random() * 46));
    }, 80);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.abort();
    stopBarAnimation();
    setState("idle");
    setTranscript("");
  }, [stopBarAnimation]);

  const startListening = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return alert("Navegador não suporta reconhecimento de voz.");
    const recognition = new SR();
    recognition.lang           = "pt-BR";
    recognition.interimResults = true;
    recognition.onstart  = () => { setState("listening"); setTranscript(""); startBarAnimation(); };
    recognition.onresult = (event: any) => {
      let t = "";
      for (let i = event.resultIndex; i < event.results.length; i++) t += event.results[i][0].transcript;
      setTranscript(t);
    };
    recognition.onend    = () => { stopBarAnimation(); setState("processing"); };
    recognition.onerror  = () => stopListening();
    recognition.start();
    recognitionRef.current = recognition;
  }, [startBarAnimation, stopBarAnimation, stopListening]);

  return { state, setState, transcript, setTranscript, barHeights, startListening, stopListening };
}

// ─── Hook: TTS via Web Speech API ─────────────────────────────────────────────
//
// CORREÇÃO Bug 3: cancelledRef não usa mais setTimeout para reset.
// Em vez disso, cada sessão de TTS recebe um "generation ID" numérico.
// O enqueue e o processQueue verificam se o ID ainda é o corrente —
// se não for, a utterance pertence a uma sessão antiga e é silenciada.
//
// Isso elimina a race condition de 50ms onde tokens novos chegavam
// durante o reset do cancelledRef e passavam pela guarda errada.

function useTTS(gender: "feminina" | "masculina") {
  const [speaking, setSpeaking] = useState(false);
  const queueRef      = useRef<string[]>([]);
  const speakingRef   = useRef(false);
  // Generation ID: incrementado a cada cancel(). Utterances antigas
  // capturam o ID no closure e são ignoradas se o ID mudar.
  const generationRef = useRef(0);

  const cancel = useCallback(() => {
    generationRef.current += 1; // invalida TODOS os callbacks pendentes
    window.speechSynthesis?.cancel();
    queueRef.current = [];
    speakingRef.current = false;
    setSpeaking(false);
  }, []);

  const pickVoice = useCallback((): SpeechSynthesisVoice | null => {
    if (typeof window === "undefined") return null;
    const voices = window.speechSynthesis.getVoices();
    const pt = voices.filter(v => v.lang.startsWith("pt"));
    if (!pt.length) return null;
    const femKeys = ["francisca", "vitória", "luciana", "female", "feminina"];
    const masKeys = ["daniel", "ricardo", "jorge", "male", "masculino"];
    const keys    = gender === "feminina" ? femKeys : masKeys;
    return pt.find(v => keys.some(k => v.name.toLowerCase().includes(k))) ?? pt[0];
  }, [gender]);

  const processQueue = useCallback((gen: number) => {
    // CORREÇÃO Bug 3: verifica geração — ignora se foi cancelado
    if (gen !== generationRef.current) return;
    if (speakingRef.current) return;

    const next = queueRef.current.shift();
    if (!next) {
      setSpeaking(false);
      speakingRef.current = false;
      return;
    }

    speakingRef.current = true;
    setSpeaking(true);

    const utt   = new SpeechSynthesisUtterance(next);
    utt.lang    = "pt-BR";
    utt.rate    = 1.0;
    utt.pitch   = gender === "feminina" ? 1.1 : 0.85;
    const voice = pickVoice();
    if (voice) utt.voice = voice;

    // Captura a geração no closure — se cancelar, gen != generationRef.current
    utt.onend = utt.onerror = () => {
      speakingRef.current = false;
      processQueue(gen);
    };

    window.speechSynthesis.speak(utt);
  }, [gender, pickVoice]);

  const enqueue = useCallback((text: string) => {
    if (!text.trim() || typeof window === "undefined") return;
    queueRef.current.push(text.trim());
    processQueue(generationRef.current);
  }, [processQueue]);

  // Expõe o generation atual para o waitAndReset verificar
  const getGeneration = useCallback(() => generationRef.current, []);

  return { enqueue, cancel, speaking, getGeneration };
}

// ─── Utilitário: divide texto em sentenças completas ──────────────────────────

function splitSentences(text: string): [string[], string] {
  const re = /[.!?]+(?:\s|$)/g;
  const sentences: string[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    const sentence = text.slice(lastIndex, match.index + match[0].length).trim();
    if (sentence) sentences.push(sentence);
    lastIndex = match.index + match[0].length;
  }
  return [sentences, text.slice(lastIndex)];
}

// ─── Página Principal do Totem ────────────────────────────────────────────────

export default function TotemPage() {
  const [totemFaqs,   setTotemFaqs]   = useState<Faq[]>([]);
  const [aiResponse,  setAiResponse]  = useState("");
  const [typedQuestion, setTypedQuestion] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [voiceGender, setVoiceGender] = useState<"feminina" | "masculina">("feminina");

  const { state, setState, transcript, setTranscript, barHeights, startListening, stopListening } =
    useSpeechRecognition();

  const { enqueue, cancel, speaking, getGeneration } = useTTS(voiceGender);

  const pendingTextRef = useRef("");

  // CORREÇÃO Bug 2: ref para o AbortController do stream em curso.
  // Ao iniciar uma nova pergunta, o stream anterior é abortado antes
  // de qualquer novo setState — garante que callbacks do stream antigo
  // não escrevem sobre a nova resposta.
  const abortControllerRef = useRef<AbortController | null>(null);

  const transcriptRef = useRef(transcript);
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

  useEffect(() => {
    const cachedFaqs = localStorage.getItem("echomind_offline_faqs");
    if (cachedFaqs) {
      try { setTotemFaqs(JSON.parse(cachedFaqs)); } catch {}
    }

    faqApi.listTotem()
      .then((faqs) => {
        setTotemFaqs(faqs);
        localStorage.setItem("echomind_offline_faqs", JSON.stringify(faqs.slice(0, 20)));
      })
      .catch(() => {});
    configApi.get()
      .then(cfg => {
        if (cfg.totem_voice_gender === "masculina" || cfg.totem_voice_gender === "feminina") {
          setVoiceGender(cfg.totem_voice_gender);
        }
      })
      .catch(() => {});
  }, []);

  const resetToIdle = useCallback(() => {
    // CORREÇÃO Bug 2: aborta stream em curso antes de resetar
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    cancel();
    pendingTextRef.current = "";
    setState("idle");
    setTranscript("");
    setAiResponse("");
    setFeedbackSent(false);
  }, [cancel, setState, setTranscript]);

  const sendToAI = useCallback(async (text: string) => {
    if (!text.trim()) { setState("idle"); return; }
    setLastQuestion(text.trim());
    setFeedbackSent(false);

    // CORREÇÃO Bug 2: cancela qualquer stream anterior antes de começar
    abortControllerRef.current?.abort();
    cancel(); // cancela TTS da resposta anterior também

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setState("responding");
    setAiResponse("");
    pendingTextRef.current = "";

    await streamChat(
      text,

      // onToken
      (token) => {
        // CORREÇÃO Bug 2: ignora tokens de streams abortados
        if (controller.signal.aborted) return;

        setAiResponse(prev => prev + token);
        const accumulated = pendingTextRef.current + token;
        const [complete, rest] = splitSentences(accumulated);
        complete.forEach(s => enqueue(s));
        pendingTextRef.current = rest;
      },

      // onDone
      () => {
        if (controller.signal.aborted) return;

        const remaining = pendingTextRef.current.trim();
        if (remaining) enqueue(remaining);
        pendingTextRef.current = "";

        // CORREÇÃO Bug 1 + Bug 5: guarda a geração TTS no momento do onDone.
        // O waitAndReset só executa o reset se a geração não mudou —
        // isso garante que uma interrupção do usuário (que chama cancel(),
        // incrementando a geração) impede que este timeout resetar o estado
        // de uma resposta nova que está chegando.
        const genAtDone = getGeneration();

        const waitAndReset = () => {
          if (controller.signal.aborted) return;
          // Geração mudou = usuário interrompeu = não reseta
          if (getGeneration() !== genAtDone) return;
          if (window.speechSynthesis?.speaking) {
            setTimeout(waitAndReset, 200);
          } else {
            setTimeout(() => {
              // Verifica de novo após o delay final — pode ter mudado
              if (!controller.signal.aborted && getGeneration() === genAtDone) {
                resetToIdle();
              }
            }, 1500);
          }
        };
        setTimeout(waitAndReset, 200);
      },

      // onError
      () => {
        if (controller.signal.aborted) return;
        const errMsg = "Desculpe, não consegui processar. Tente novamente.";
        setAiResponse(errMsg);
        enqueue(errMsg);
        setTimeout(resetToIdle, 4000);
      }
    );
  }, [setState, enqueue, cancel, getGeneration, resetToIdle]);

  // CORREÇÃO Bug 4: handleFaqClick não chama sendToAI diretamente.
  // Passa pelo estado "processing" — o useEffect abaixo detecta a
  // transição e chama sendToAI de forma controlada, assim como o
  // fluxo de voz. Isso garante que nunca há dois sendToAI simultâneos.
  const handleFaqClick = useCallback((question: string) => {
    // Se já está respondendo, interrompe primeiro
    if (state === "responding") {
      abortControllerRef.current?.abort();
      cancel();
    }
    setTranscript(question);
    setState("processing");
  }, [state, cancel, setTranscript, setState]);

  useEffect(() => {
    if (state === "processing") {
      const text = transcriptRef.current;
      if (text) sendToAI(text);
      else setState("idle");
    }
  }, [state, sendToAI, setState]);

  const submitTypedQuestion = () => {
    const question = typedQuestion.trim();
    if (!question) return;
    setTypedQuestion("");
    setTranscript(question);
    setState("processing");
  };

  const sendFeedback = async (helpful: boolean) => {
    if (!lastQuestion || !aiResponse || feedbackSent) return;
    setFeedbackSent(true);
    try {
      await feedbackApi.save({ question: lastQuestion, answer: aiResponse, helpful });
    } catch {
      // O feedback é complementar; a interação principal não deve ser bloqueada.
    }
  };

  const isActive = state !== "idle";

  return (
    <div className="totem-root">
      <div className="bg-dots" />
      <div className="bg-fade" />

      <main
        className="totem-main"
        style={{
          opacity: isActive ? 0 : 1,
          pointerEvents: isActive ? "none" : "all",
          transform: isActive ? "scale(0.95)" : "scale(1)",
        }}
      >
        <section className="hero-section">
          
          <h1 className="hero-title">
            Olá! Como posso <br />
            <span className="title-accent">te ajudar hoje?</span>
          </h1>
          <div className="pulse-wrapper">
            <button className="cta-button" onClick={startListening}>
              <Mic className="cta-icon" strokeWidth={1.5} />
              <span className="cta-label">Falar agora</span>
            </button>
          </div>

          <div className="text-chat">
            <Keyboard className="text-chat-icon" size={18} strokeWidth={1.8} aria-hidden="true" />
            <input
              value={typedQuestion}
              onChange={(event) => setTypedQuestion(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && submitTypedQuestion()}
              placeholder="Ou digite sua dúvida aqui..."
              className="text-chat-input"
            />
            <button className="text-chat-button" onClick={submitTypedQuestion} aria-label="Enviar pergunta">
              <Send size={18} />
            </button>
          </div>
        </section>

        {totemFaqs.length > 0 && (
          <section className="faqs-section">
            <p className="faqs-label">Perguntas frequentes</p>
            <div className="faqs-grid">
              {totemFaqs.map((faq) => (
                <button
                  key={faq.id}
                  className="faq-card"
                  onClick={() => handleFaqClick(faq.question)}
                >
                  <span className="faq-icon">💬</span>
                  <span className="faq-text">{faq.question}</span>
                  <ChevronRight className="faq-arrow" size={14} />
                </button>
              ))}
            </div>
          </section>
        )}
      </main>

      <div
        className="listen-overlay"
        style={{
          opacity: isActive ? 1 : 0,
          pointerEvents: isActive ? "all" : "none",
          visibility: isActive ? "visible" : "hidden",
        }}
      >
        {(state === "listening" || state === "processing") && (
          <div className="wave-wrap">
            {barHeights.map((h, i) => (
              <div key={i} className="bar" style={{ height: state === "listening" ? `${h}px` : "4px" }} />
            ))}
          </div>
        )}

        {state === "responding" && speaking && (
          <div className="speaking-indicator">
            <Volume2 className="speaking-icon" size={28} />
          </div>
        )}

        <p className="listen-status">
          {state === "listening"  && "Ouvindo…"}
          {state === "processing" && "Processando…"}
          {state === "responding" && (speaking ? "Falando…" : "Respondendo…")}
        </p>

        {state === "responding" ? (
          <div className="ai-response-box">
            <p className="ai-response-text">{aiResponse}</p>
            {aiResponse && !feedbackSent && (
              <div className="feedback-row">
                <span>Essa resposta ajudou?</span>
                <button onClick={() => sendFeedback(true)}><ThumbsUp size={16} /> Sim</button>
                <button onClick={() => sendFeedback(false)}><ThumbsDown size={16} /> Não</button>
              </div>
            )}
            {feedbackSent && <p className="feedback-thanks">Obrigado pelo feedback.</p>}
          </div>
        ) : (
          <p className="listen-transcript">
            {transcript || "..."}
            {state === "listening" && <span className="cursor" />}
          </p>
        )}

        {state === "listening" && (
          <button className="stop-btn" onClick={stopListening}>
            <X size={14} /> Cancelar
          </button>
        )}

        {state === "responding" && (
          <button className="stop-btn" onClick={resetToIdle}>
            {speaking ? <VolumeX size={14} /> : <X size={14} />}
            {speaking ? "Parar Áudio" : "Fechar"}
          </button>
        )}
      </div>

      <style>{`
        .totem-root{position:relative;min-height:100vh;width:100%;background:#fff;color:#172033;font-family:Inter,system-ui,sans-serif;display:flex;flex-direction:column;overflow:hidden}
        .bg-dots{position:absolute;inset:0;background-image:radial-gradient(circle,rgba(1,166,253,.08) 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(to bottom,black,transparent 72%)}
        .bg-fade{position:absolute;inset:0;background:linear-gradient(180deg,#f6fbff 0%,rgba(246,251,255,.42) 38%,#fff 100%)}
        .totem-main{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:46px;padding:40px;transition:all .4s ease}
        .hero-section{display:flex;flex-direction:column;align-items:center;text-align:center;gap:18px;width:min(920px,92vw)}
        .hero-eyebrow{font-size:12px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:#0277bd;background:#eef9ff;border:1px solid #ccecff;padding:8px 14px;border-radius:999px}
        .hero-title{font-size:clamp(42px,7vw,78px);font-weight:800;color:#172033;line-height:1.02;letter-spacing:0;text-shadow:none}
        .title-accent{color:#01a6fd}
        .pulse-wrapper{position:relative;width:164px;height:164px;display:flex;align-items:center;justify-content:center;margin-top:12px}
        .cta-button{position:relative;z-index:2;width:146px;height:146px;border-radius:50%;background:#01a6fd;border:1px solid #01a6fd;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 18px 40px rgba(1,166,253,.24);transition:transform .2s,border-color .2s,background .2s,box-shadow .2s}
        .cta-button:hover{transform:translateY(-3px);border-color:#0186cc;background:#0195e4;box-shadow:0 22px 48px rgba(1,166,253,.28)}
        .cta-button:active{transform:scale(.96)}
        .cta-icon{color:#fff;width:34px;height:34px}
        .cta-label{font-size:11px;font-weight:800;text-transform:uppercase;color:#fff;margin-top:8px;letter-spacing:.08em}
        .text-chat{display:flex;align-items:center;width:min(720px,92vw);padding:8px 8px 8px 18px;border:1px solid #dceaf4;border-radius:999px;background:#fff;box-shadow:0 14px 42px rgba(24,49,83,.10)}
        .text-chat-icon{flex:0 0 auto;color:#7b8da3}
        .text-chat-input{flex:1;border:0;outline:0;background:transparent;color:#172033;padding:15px 14px;font-size:16px}
        .text-chat-input::placeholder{color:#7b8da3}
        .text-chat-button{display:flex;align-items:center;justify-content:center;width:46px;height:46px;border:0;border-radius:50%;background:#01a6fd;color:#fff;cursor:pointer;box-shadow:0 10px 28px rgba(1,166,253,.30)}
        .faqs-section{width:100%;max-width:880px;display:flex;flex-direction:column;gap:18px}
        .faqs-label{font-size:11px;font-weight:700;text-transform:uppercase;color:#7b8da3;text-align:center;letter-spacing:.18em}
        .faqs-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
        .faq-card{display:flex;align-items:center;gap:14px;padding:18px 20px;border-radius:8px;background:#fff;border:1px solid #e3edf5;color:#172033;cursor:pointer;text-align:left;transition:all .2s;box-shadow:0 10px 28px rgba(24,49,83,.06)}
        .faq-card:hover{border-color:#8edcff;transform:translateY(-2px);background:#f7fcff;box-shadow:0 14px 34px rgba(1,166,253,.12)}
        .faq-icon{font-size:20px}
        .faq-text{flex:1;font-weight:600;font-size:14px;color:#233249}
        .faq-arrow{color:#01a6fd}
        .listen-overlay{position:absolute;inset:0;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(180deg,#f6fbff 0%,#fff 100%);transition:all .4s ease;gap:28px;padding:40px}
        .wave-wrap{display:flex;gap:7px;height:86px;align-items:center}
        .bar{width:7px;background:linear-gradient(#70d3ff,#01a6fd);border-radius:12px;transition:height .1s ease;box-shadow:0 0 18px rgba(1,166,253,.28)}
        .speaking-indicator{display:flex;align-items:center;justify-content:center;width:68px;height:68px;border-radius:50%;background:#eef9ff;border:2px solid #9fe2ff;animation:speakPulse 1s ease-in-out infinite}
        .speaking-icon{color:#01a6fd}
        @keyframes speakPulse{0%,100%{transform:scale(1);opacity:.8}50%{transform:scale(1.1);opacity:1}}
        .listen-status{font-weight:800;color:#0277bd;text-transform:uppercase;letter-spacing:.2em;font-size:13px}
        .listen-transcript{font-size:30px;font-weight:700;text-align:center;max-width:80%;line-height:1.35;color:#172033}
        .ai-response-box{max-width:min(900px,86vw);background:#fff;border:1px solid #dceaf4;border-radius:16px;padding:30px 34px;box-shadow:0 24px 70px rgba(24,49,83,.12)}
        .ai-response-text{font-size:21px;font-weight:500;line-height:1.65;color:#233249;text-align:center;white-space:pre-wrap}
        .feedback-row{display:flex;align-items:center;justify-content:center;gap:10px;margin-top:22px;color:#6c7c90;font-size:14px}
        .feedback-row button{display:inline-flex;align-items:center;gap:6px;border:1px solid #dceaf4;background:#fff;color:#233249;border-radius:999px;padding:9px 13px;cursor:pointer}
        .feedback-row button:hover{border-color:#01a6fd;background:#f2fbff}
        .feedback-thanks{text-align:center;color:#0277bd;font-size:14px;margin-top:18px}
        .cursor{display:inline-block;width:3px;height:1em;background:#01a6fd;margin-left:5px;animation:blink .8s infinite;vertical-align:middle}
        @keyframes blink{50%{opacity:0}}
        .stop-btn{display:flex;align-items:center;gap:8px;padding:12px 24px;border-radius:30px;border:1px solid #b7e7fb;color:#0277bd;background:#fff;cursor:pointer;font-weight:700;font-size:13px;box-shadow:0 10px 28px rgba(24,49,83,.08)}
        @media(max-width:720px){.faqs-grid{grid-template-columns:1fr}.totem-main{gap:30px}.listen-transcript{font-size:24px}.ai-response-text{font-size:18px}.feedback-row{flex-wrap:wrap}.pulse-wrapper{width:154px;height:154px}.cta-button{width:124px;height:124px}}
      `}</style>
    </div>
  );
}

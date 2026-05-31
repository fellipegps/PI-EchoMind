"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Mic, ChevronRight, X, Volume2, VolumeX } from "lucide-react";
import { streamChat, faqApi, configApi } from "@/lib/api";
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
    faqApi.listTotem().then(setTotemFaqs).catch(() => {});
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
  }, [cancel, setState, setTranscript]);

  const sendToAI = useCallback(async (text: string) => {
    if (!text.trim()) { setState("idle"); return; }

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
          <p className="hero-eyebrow">Assistente Virtual</p>
          <h1 className="hero-title">
            Olá! Como posso <br />
            <span className="title-accent">te ajudar hoje?</span>
          </h1>
          <div className="pulse-wrapper">
            <div className="pulse-ring pulse-before" />
            <div className="pulse-ring pulse-after" />
            <button className="cta-button" onClick={startListening}>
              <Mic className="cta-icon" strokeWidth={1.5} />
              <span className="cta-label">Iniciar Conversa</span>
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

      <footer className="totem-footer">Powered by EchoMind AI</footer>

      <style>{`
        .totem-root{position:relative;min-height:100vh;width:100%;background:#f8f8f6;color:#1a1a1a;font-family:sans-serif;display:flex;flex-direction:column;overflow:hidden}
        .bg-dots{position:absolute;inset:0;background-image:radial-gradient(circle,rgba(0,0,0,.07) 1px,transparent 1px);background-size:28px 28px}
        .bg-fade{position:absolute;inset:0;background:radial-gradient(ellipse 90% 55% at 50% 0%,rgba(255,255,255,.95) 0%,transparent 70%)}
        .totem-main{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:60px;padding:40px;transition:all .4s ease}
        .hero-section{display:flex;flex-direction:column;align-items:center;text-align:center;gap:16px}
        .hero-eyebrow{font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:#8a8a8a}
        .hero-title{font-size:50px;font-weight:700;color:#111;line-height:1.1}
        .title-accent{color:#01a6fd}
        .pulse-wrapper{position:relative;width:180px;height:180px;display:flex;align-items:center;justify-content:center;margin-top:20px}
        .pulse-ring{position:absolute;width:100%;height:100%;background-color:#01a6fd;border-radius:50%;z-index:1;opacity:.4;animation:pulse 2s ease-out infinite}
        .pulse-after{animation-delay:1s}
        @keyframes pulse{100%{transform:scale(1.5);opacity:0}}
        .cta-button{position:relative;z-index:2;width:140px;height:140px;border-radius:50%;background:#fff;border:1px solid #ddd;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.08);transition:transform .2s}
        .cta-button:active{transform:scale(.95)}
        .cta-icon{color:#01a6fd;width:32px;height:32px}
        .cta-label{font-size:10px;font-weight:700;text-transform:uppercase;color:#999;margin-top:5px}
        .faqs-section{width:100%;max-width:800px;display:flex;flex-direction:column;gap:20px}
        .faqs-label{font-size:11px;font-weight:600;text-transform:uppercase;color:#bbb;text-align:center;letter-spacing:1px}
        .faqs-grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}
        .faq-card{display:flex;align-items:center;gap:15px;padding:20px;border-radius:12px;background:#fff;border:1px solid #eee;cursor:pointer;text-align:left;transition:all .2s}
        .faq-card:hover{border-color:#01a6fd;transform:translateY(-2px)}
        .faq-icon{font-size:20px}
        .faq-text{flex:1;font-weight:500;font-size:14px}
        .faq-arrow{color:#ccc}
        .listen-overlay{position:absolute;inset:0;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f8f8f6;transition:all .4s ease;gap:30px;padding:40px}
        .wave-wrap{display:flex;gap:6px;height:80px;align-items:center}
        .bar{width:6px;background:#01a6fd;border-radius:10px;transition:height .1s ease}
        .speaking-indicator{display:flex;align-items:center;justify-content:center;width:60px;height:60px;border-radius:50%;background:#01a6fd12;border:2px solid #01a6fd40;animation:speakPulse 1s ease-in-out infinite}
        .speaking-icon{color:#01a6fd}
        @keyframes speakPulse{0%,100%{transform:scale(1);opacity:.8}50%{transform:scale(1.1);opacity:1}}
        .listen-status{font-weight:700;color:#01a6fd;text-transform:uppercase;letter-spacing:2px;font-size:14px}
        .listen-transcript{font-size:26px;font-weight:600;text-align:center;max-width:80%;line-height:1.4;color:#333}
        .ai-response-box{max-width:80%;background:#fff;border:1px solid #e5e5e5;border-radius:20px;padding:28px 32px;box-shadow:0 4px 30px rgba(0,0,0,.06)}
        .ai-response-text{font-size:20px;font-weight:500;line-height:1.6;color:#222;text-align:center;white-space:pre-wrap}
        .cursor{display:inline-block;width:3px;height:1em;background:#01a6fd;margin-left:5px;animation:blink .8s infinite;vertical-align:middle}
        @keyframes blink{50%{opacity:0}}
        .stop-btn{display:flex;align-items:center;gap:8px;padding:12px 24px;border-radius:30px;border:1px solid #01a6fd;color:#01a6fd;background:#fff;cursor:pointer;font-weight:600;font-size:13px}
        .totem-footer{position:absolute;bottom:20px;width:100%;text-align:center;color:#aaa;font-size:12px;z-index:5}
      `}</style>
    </div>
  );
}

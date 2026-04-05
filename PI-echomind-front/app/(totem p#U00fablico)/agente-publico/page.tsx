"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Mic, ChevronRight, X } from "lucide-react";

// ─── Tipos e Globais ──────────────────────────────────────────────────────────
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

type ListeningState = "idle" | "listening" | "processing";

const BAR_COUNT = 12;
const FAQS_MOCK = [
  { id: 1, question: "Como faço minha matrícula?", icon: "📋" },
  { id: 2, question: "Quais são os horários da secretaria?",   icon: "🕐" },
  { id: 3, question: "Como solicitar meu histórico escolar?",  icon: "📄" },
  { id: 4, question: "Como acessar o portal do aluno?",        icon: "💻" },
];

// ─── Hook de Reconhecimento de Voz ───────────────────────────────────────────
function useSpeechRecognition(onSpeechEnd?: (text: string) => void) {
  const [state, setState] = useState<ListeningState>("idle");
  const [transcript, setTranscript] = useState("");
  const [barHeights, setBarHeights] = useState<number[]>(Array(BAR_COUNT).fill(8));

  const recognitionRef = useRef<any>(null);
  const barAnimRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return alert("Navegador não suportado");

    const recognition = new SpeechRecognition();
    recognition.lang = "pt-BR";
    recognition.interimResults = true;

    recognition.onstart = () => {
      setState("listening");
      setTranscript("");
      startBarAnimation();
    };

    recognition.onresult = (event: any) => {
      let current = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        current += event.results[i][0].transcript;
      }
      setTranscript(current);
    };

    recognition.onend = () => {
      if (state === "idle") return; 
      setState("processing");
      stopBarAnimation();
      if (onSpeechEnd) onSpeechEnd(transcript); 
    };

    recognition.onerror = () => stopListening();
    recognition.start();
    recognitionRef.current = recognition;
  }, [startBarAnimation, stopBarAnimation, stopListening, transcript, state, onSpeechEnd]);

  return { state, transcript, barHeights, startListening, stopListening, setState };
}

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function TotemPage() {
  const { state, transcript, barHeights, startListening, stopListening, setState } = useSpeechRecognition(
    (text) => {
      console.log("Enviando para API:", text);
      // Simula tempo de resposta da API
      setTimeout(() => setState("idle"), 3000); 
    }
  );

  const isActive = state !== "idle";

  return (
    <div className="totem-root">
      <div className="bg-dots" />
      <div className="bg-fade" />

      {/* View Principal (Idle) */}
      <main className="totem-main" style={{ 
        opacity: isActive ? 0 : 1, 
        pointerEvents: isActive ? "none" : "all",
        transform: isActive ? "scale(0.95)" : "scale(1)"
      }}>
        <section className="hero-section">
          <p className="hero-eyebrow">Assistente Virtual</p>
          <h1 className="hero-title">Olá! Como posso <br /> <span className="title-accent">te ajudar hoje?</span></h1>
          
          <div className="pulse-wrapper">
            {/* Os anéis de pulso baseados na sua foto */}
            <div className="pulse-ring pulse-before" />
            <div className="pulse-ring pulse-after" />
            
            <button className="cta-button" onClick={startListening}>
              <Mic className="cta-icon" strokeWidth={1.5} />
              <span className="cta-label">Iniciar Conversa</span>
            </button>
          </div>
        </section>

        <section className="faqs-section">
          <p className="faqs-label">Perguntas frequentes</p>
          <div className="faqs-grid">
            {FAQS_MOCK.map((faq) => (
              <button key={faq.id} className="faq-card">
                <span className="faq-icon">{faq.icon}</span>
                <span className="faq-text">{faq.question}</span>
                <ChevronRight className="faq-arrow" size={14} />
              </button>
            ))}
          </div>
        </section>
      </main>

      {/* Overlay de Escuta/Processamento */}
      <div className="listen-overlay" style={{ 
        opacity: isActive ? 1 : 0, 
        pointerEvents: isActive ? "all" : "none",
        visibility: isActive ? "visible" : "hidden"
      }}>
        <div className="wave-wrap">
          {barHeights.map((h, i) => (
            <div
              key={i}
              className="bar"
              style={{
                height: state === "listening" ? `${h}px` : "4px",
                animationDelay: `${(i * 0.06).toFixed(2)}s`,
              }}
            />
          ))}
        </div>
        <p className="listen-status">{state === "listening" ? "Ouvindo…" : "Processando…"}</p>
        <p className="listen-transcript">
          {transcript || "..."}
          {state === "listening" && <span className="cursor" />}
        </p>
        
        {state === "listening" && (
          <button className="stop-btn" onClick={stopListening}>
            <X size={14} /> Cancelar
          </button>
        )}
      </div>

      <footer className="totem-footer">Powered by EchoMind AI</footer>

      <style>{`
        .totem-root { position: relative; min-height: 100vh; width: 100%; background: #f8f8f6; color: #1a1a1a; font-family: sans-serif; display: flex; flex-direction: column; overflow: hidden; }
        .bg-dots { position: absolute; inset: 0; background-image: radial-gradient(circle, rgba(0,0,0,.07) 1px, transparent 1px); background-size: 28px 28px; }
        .bg-fade { position: absolute; inset: 0; background: radial-gradient(ellipse 90% 55% at 50% 0%, rgba(255,255,255,.95) 0%, transparent 70%); }
        
        .totem-main { position: absolute; inset: 0; z-index: 2; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 60px; padding: 40px; transition: all .4s ease; }
        .hero-section { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 16px; }
        .hero-eyebrow { font-size: 12px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: #8a8a8a; }
        .hero-title { font-size: 50px; font-weight: 700; color: #111; line-height: 1.1; }
        .title-accent { color: #01a6fd; }

        /* ── Efeito de Pulso da Foto ── */
        .pulse-wrapper { 
          position: relative; 
          width: 180px; 
          height: 180px; 
          display: flex; 
          align-items: center; 
          justify-content: center; 
          margin-top: 20px; 
        }

        .pulse-ring {
          content: "";
          position: absolute;
          width: 100%;
          height: 100%;
          background-color: #01a6fd;
          border-radius: 50%;
          z-index: 1;
          opacity: 0.4;
          animation: pulse 2s ease-out infinite;
        }

        .pulse-after {
          animation-delay: 1s;
        }

        @keyframes pulse {
          100% {
            transform: scale(1.5);
            opacity: 0;
          }
        }

        .cta-button { 
          position: relative; 
          z-index: 2;
          width: 140px; 
          height: 140px; 
          border-radius: 50%; 
          background: #fff; 
          border: 1px solid #ddd; 
          display: flex; 
          flex-direction: column; 
          align-items: center; 
          justify-content: center; 
          cursor: pointer; 
          box-shadow: 0 4px 20px rgba(0,0,0,0.08);
          transition: transform 0.2s;
        }
        .cta-button:active { transform: scale(0.95); }
        .cta-icon { color: #01a6fd; width: 32px; height: 32px; }
        .cta-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #999; margin-top: 5px; }

        /* ── Restante da UI ── */
        .faqs-section { width: 100%; max-width: 800px; display: flex; flex-direction: column; gap: 20px; }
        .faqs-label { font-size: 11px; font-weight: 600; text-transform: uppercase; color: #bbb; text-align: center; letter-spacing: 1px; }
        .faqs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .faq-card { display: flex; align-items: center; gap: 15px; padding: 20px; border-radius: 12px; background: #fff; border: 1px solid #eee; cursor: pointer; text-align: left; transition: all 0.2s; }
        .faq-card:hover { border-color: #01a6fd; transform: translateY(-2px); }
        .faq-icon { font-size: 20px; }
        .faq-text { flex: 1; font-weight: 500; font-size: 14px; }
        .faq-arrow { color: #ccc; }

        .listen-overlay { position: absolute; inset: 0; z-index: 10; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #f8f8f6; transition: all .4s ease; gap: 30px; }
        .wave-wrap { display: flex; gap: 6px; height: 80px; align-items: center; }
        .bar { width: 6px; background: #01a6fd; border-radius: 10px; transition: height 0.1s ease; }
        .listen-status { font-weight: 700; color: #01a6fd; text-transform: uppercase; letter-spacing: 2px; font-size: 14px; }
        .listen-transcript { font-size: 26px; font-weight: 600; text-align: center; max-width: 80%; line-height: 1.4; color: #333; }
        .cursor { display: inline-block; width: 3px; height: 1em; background: #01a6fd; margin-left: 5px; animation: blink .8s infinite; vertical-align: middle; }
        @keyframes blink { 50% { opacity: 0; } }

        .stop-btn { display: flex; align-items: center; gap: 8px; padding: 12px 24px; border-radius: 30px; border: 1px solid #01a6fd; color: #01a6fd; background: #fff; cursor: pointer; font-weight: 600; font-size: 13px; }
        .totem-footer { position: absolute; bottom: 20px; width: 100%; text-align: center; color: #aaa; font-size: 12px; z-index: 5; }
      `}</style>
    </div>
  );
}
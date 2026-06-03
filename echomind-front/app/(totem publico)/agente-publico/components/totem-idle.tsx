"use client";

import type { CSSProperties } from "react";
import { ChevronRight, Keyboard, Mic, Send } from "lucide-react";
import type { Faq } from "@/lib/api";

type TotemIdleProps = {
  totemFaqs: Faq[];
  typedQuestion: string;
  onTypedQuestionChange: (value: string) => void;
  onSubmitTyped: () => void;
  onFaqClick: (question: string) => void;
  onStartListening: () => void;
  style?: CSSProperties;
};

export function TotemIdle({
  totemFaqs,
  typedQuestion,
  onTypedQuestionChange,
  onSubmitTyped,
  onFaqClick,
  onStartListening,
  style,
}: TotemIdleProps) {
  return (
    <main className="totem-main" style={style}>
      <section className="hero-section">
        <h1 className="hero-title">
          Olá! Como posso <br />
          <span className="title-accent">te ajudar hoje?</span>
        </h1>
        <div className="pulse-wrapper">
          <button className="cta-button" onClick={onStartListening}>
            <Mic className="cta-icon" strokeWidth={1.5} />
            <span className="cta-label">Falar agora</span>
          </button>
        </div>

        <div className="text-chat">
          <Keyboard className="text-chat-icon" size={18} strokeWidth={1.8} aria-hidden="true" />
          <input
            value={typedQuestion}
            onChange={(event) => onTypedQuestionChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") onSubmitTyped();
            }}
            placeholder="Ou digite sua dúvida aqui..."
            className="text-chat-input"
          />
          <button className="text-chat-button" onClick={onSubmitTyped} aria-label="Enviar pergunta">
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
                onClick={() => onFaqClick(faq.question)}
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
  );
}


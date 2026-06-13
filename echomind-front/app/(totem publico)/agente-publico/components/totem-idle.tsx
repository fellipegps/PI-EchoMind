"use client";

import { useState } from "react";
import type { CSSProperties } from "react";
import { ChevronRight, Keyboard, Mic, Send } from "lucide-react";
import type { Faq } from "@/lib/api";
import { VirtualKeyboard } from "./virtual-keyboard";

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
  const [keyboardOpen, setKeyboardOpen] = useState(false);

  const handleSubmitTyped = () => {
    onSubmitTyped();
    setKeyboardOpen(false);
  };

  const hasFaqs = totemFaqs.length > 0;

  return (
    <main className={`totem-main ${hasFaqs ? "totem-main--with-faqs" : "totem-main--empty"}`} style={style}>
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

        <div className="text-chat-area">
          <div className="text-chat">
            <Keyboard className="text-chat-icon" size={18} strokeWidth={1.8} aria-hidden="true" />
            <input
              value={typedQuestion}
              onChange={(event) => onTypedQuestionChange(event.target.value)}
              onFocus={() => setKeyboardOpen(true)}
              onClick={() => setKeyboardOpen(true)}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleSubmitTyped();
              }}
              placeholder="Ou digite sua dúvida aqui..."
              className="text-chat-input"
            />
            <button className="text-chat-button" onClick={handleSubmitTyped} aria-label="Enviar pergunta">
              <Send size={18} />
            </button>
          </div>

          <VirtualKeyboard
            value={typedQuestion}
            isOpen={keyboardOpen}
            onChange={onTypedQuestionChange}
            onSubmit={handleSubmitTyped}
            onClose={() => setKeyboardOpen(false)}
          />
        </div>
      </section>

      {hasFaqs && (
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

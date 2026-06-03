"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { feedbackApi, streamChat } from "@/lib/api";
import type { Dispatch, SetStateAction } from "react";
import type { ListeningState } from "../types";
import { splitSentences } from "../utils/speech";

type UseTotemChatParams = {
  enqueue: (text: string) => void;
  cancel: () => void;
  getGeneration: () => number;
  state: ListeningState;
  setState: Dispatch<SetStateAction<ListeningState>>;
  transcript: string;
  setTranscript: Dispatch<SetStateAction<string>>;
};

export function useTotemChat({
  enqueue,
  cancel,
  getGeneration,
  state,
  setState,
  transcript,
  setTranscript,
}: UseTotemChatParams) {
  const [aiResponse, setAiResponse] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);

  const pendingTextRef = useRef("");

  // CORREÇÃO Bug 2: ref para o AbortController do stream em curso.
  // Ao iniciar uma nova pergunta, o stream anterior é abortado antes
  // de qualquer novo setState — garante que callbacks do stream antigo
  // não escrevem sobre a nova resposta.
  const abortControllerRef = useRef<AbortController | null>(null);

  const transcriptRef = useRef(transcript);
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

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

  const submitTypedQuestion = useCallback((typedQuestion: string, setTypedQuestion: (value: string) => void) => {
    const question = typedQuestion.trim();
    if (!question) return;
    setTypedQuestion("");
    setTranscript(question);
    setState("processing");
  }, [setState, setTranscript]);

  const sendFeedback = useCallback(async (helpful: boolean) => {
    if (!lastQuestion || !aiResponse || feedbackSent) return;
    setFeedbackSent(true);
    try {
      await feedbackApi.save({ question: lastQuestion, answer: aiResponse, helpful });
    } catch {
      // O feedback é complementar; a interação principal não deve ser bloqueada.
    }
  }, [aiResponse, feedbackSent, lastQuestion]);

  return {
    aiResponse,
    lastQuestion,
    feedbackSent,
    setFeedbackSent,
    resetToIdle,
    handleFaqClick,
    submitTypedQuestion,
    sendFeedback,
  };
}


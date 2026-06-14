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
  tenantId: string;
};

export function useTotemChat({
  enqueue,
  cancel,
  getGeneration,
  state,
  setState,
  transcript,
  setTranscript,
  tenantId,
}: UseTotemChatParams) {
  const [aiResponse, setAiResponse] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);

  const pendingTextRef = useRef("");
  const abortControllerRef = useRef<AbortController | null>(null);
  const transcriptRef = useRef(transcript);

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  const resetToIdle = useCallback(() => {
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
    if (!text.trim()) {
      setState("idle");
      return;
    }

    if (!tenantId) {
      const errMsg = "Link do totem invalido. Abra o link publico gerado no painel.";
      setAiResponse(errMsg);
      enqueue(errMsg);
      setTimeout(resetToIdle, 4000);
      return;
    }

    setLastQuestion(text.trim());
    setFeedbackSent(false);

    abortControllerRef.current?.abort();
    cancel();

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setState("responding");
    setAiResponse("");
    pendingTextRef.current = "";

    await streamChat(
      text,
      tenantId,
      (token) => {
        if (controller.signal.aborted) return;

        setAiResponse((prev) => prev + token);
        const accumulated = pendingTextRef.current + token;
        const [complete, rest] = splitSentences(accumulated);
        complete.forEach((sentence) => enqueue(sentence));
        pendingTextRef.current = rest;
      },
      () => {
        if (controller.signal.aborted) return;

        const remaining = pendingTextRef.current.trim();
        if (remaining) enqueue(remaining);
        pendingTextRef.current = "";

        const genAtDone = getGeneration();

        const waitAndReset = () => {
          if (controller.signal.aborted) return;
          if (getGeneration() !== genAtDone) return;

          if (window.speechSynthesis?.speaking) {
            setTimeout(waitAndReset, 200);
            return;
          }

          setTimeout(() => {
            if (!controller.signal.aborted && getGeneration() === genAtDone) {
              resetToIdle();
            }
          }, 1500);
        };

        setTimeout(waitAndReset, 200);
      },
      () => {
        if (controller.signal.aborted) return;
        const errMsg = "Desculpe, nao consegui processar. Tente novamente.";
        setAiResponse(errMsg);
        enqueue(errMsg);
        setTimeout(resetToIdle, 4000);
      }
    );
  }, [cancel, enqueue, getGeneration, resetToIdle, setState, tenantId]);

  const handleFaqClick = useCallback((question: string) => {
    if (state === "responding") {
      abortControllerRef.current?.abort();
      cancel();
    }
    setTranscript(question);
    setState("processing");
  }, [cancel, setState, setTranscript, state]);

  useEffect(() => {
    if (state === "processing") {
      const text = transcriptRef.current;
      if (text) sendToAI(text);
      else setState("idle");
    }
  }, [sendToAI, setState, state]);

  const submitTypedQuestion = useCallback((
    typedQuestion: string,
    setTypedQuestion: (value: string) => void
  ) => {
    const question = typedQuestion.trim();
    if (!question) return;
    setTypedQuestion("");
    setTranscript(question);
    setState("processing");
  }, [setState, setTranscript]);

  const sendFeedback = useCallback(async (helpful: boolean) => {
    if (!lastQuestion || !aiResponse || feedbackSent || !tenantId) return;
    setFeedbackSent(true);
    try {
      await feedbackApi.save({
        question: lastQuestion,
        answer: aiResponse,
        helpful,
        tenant_id: tenantId,
      });
    } catch {
      // Feedback is complementary; do not block the main interaction.
    }
  }, [aiResponse, feedbackSent, lastQuestion, tenantId]);

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

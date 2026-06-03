"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useTTS(gender: "feminina" | "masculina") {
  const [speaking, setSpeaking] = useState(false);
  const queueRef = useRef<string[]>([]);
  const speakingRef = useRef(false);
  const processQueueRef = useRef<(gen: number) => void>(() => {});
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
    const keys = gender === "feminina" ? femKeys : masKeys;
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

    const utt = new SpeechSynthesisUtterance(next);
    utt.lang = "pt-BR";
    utt.rate = 1.0;
    utt.pitch = gender === "feminina" ? 1.1 : 0.85;
    const voice = pickVoice();
    if (voice) utt.voice = voice;

    // Captura a geração no closure — se cancelar, gen != generationRef.current
    utt.onend = utt.onerror = () => {
      speakingRef.current = false;
      processQueueRef.current(gen);
    };

    window.speechSynthesis.speak(utt);
  }, [gender, pickVoice]);

  useEffect(() => {
    processQueueRef.current = processQueue;
  }, [processQueue]);

  const enqueue = useCallback((text: string) => {
    if (!text.trim() || typeof window === "undefined") return;
    queueRef.current.push(text.trim());
    processQueue(generationRef.current);
  }, [processQueue]);

  // Expõe o generation atual para o waitAndReset verificar
  const getGeneration = useCallback(() => generationRef.current, []);

  return { enqueue, cancel, speaking, getGeneration };
}

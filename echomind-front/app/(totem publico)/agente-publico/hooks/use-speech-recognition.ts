"use client";

import { useCallback, useRef, useState } from "react";
import {
  BAR_COUNT,
  type ListeningState,
  type SpeechRecognitionLike,
  type SpeechRecognitionResultEvent,
} from "../types";

export function useSpeechRecognition() {
  const [state, setState] = useState<ListeningState>("idle");
  const [transcript, setTranscript] = useState("");
  const [barHeights, setBarHeights] = useState<number[]>(Array(BAR_COUNT).fill(8));
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
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
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return alert("Navegador não suporta reconhecimento de voz.");
    const recognition = new SR();
    recognition.lang = "pt-BR";
    recognition.interimResults = true;
    recognition.onstart = () => {
      setState("listening");
      setTranscript("");
      startBarAnimation();
    };
    recognition.onresult = (event: SpeechRecognitionResultEvent) => {
      let t = "";
      for (let i = event.resultIndex; i < event.results.length; i++) t += event.results[i][0].transcript;
      setTranscript(t);
    };
    recognition.onend = () => {
      stopBarAnimation();
      setState("processing");
    };
    recognition.onerror = () => stopListening();
    recognition.start();
    recognitionRef.current = recognition;
  }, [startBarAnimation, stopBarAnimation, stopListening]);

  return { state, setState, transcript, setTranscript, barHeights, startListening, stopListening };
}

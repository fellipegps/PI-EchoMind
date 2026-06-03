"use client";

import { useState } from "react";
import "./totem.css";

import { ListenOverlay } from "./components/listen-overlay";
import { TotemIdle } from "./components/totem-idle";
import { useSpeechRecognition } from "./hooks/use-speech-recognition";
import { useTTS } from "./hooks/use-tts";
import { useTotemChat } from "./hooks/use-totem-chat";
import { useTotemData } from "./hooks/use-totem-data";

export default function TotemPage() {
  const [typedQuestion, setTypedQuestion] = useState("");

  const { state, setState, transcript, setTranscript, barHeights, startListening, stopListening } =
    useSpeechRecognition();

  const { totemFaqs, voiceGender } = useTotemData();

  const { enqueue, cancel, speaking, getGeneration } = useTTS(voiceGender);

  const {
    aiResponse,
    feedbackSent,
    resetToIdle,
    handleFaqClick,
    submitTypedQuestion,
    sendFeedback,
  } = useTotemChat({
    enqueue,
    cancel,
    getGeneration,
    state,
    setState,
    transcript,
    setTranscript,
  });

  const isActive = state !== "idle";

  return (
    <div className="totem-root">
      <div className="bg-dots" />
      <div className="bg-fade" />

      <TotemIdle
        totemFaqs={totemFaqs}
        typedQuestion={typedQuestion}
        onTypedQuestionChange={setTypedQuestion}
        onSubmitTyped={() => submitTypedQuestion(typedQuestion, setTypedQuestion)}
        onFaqClick={handleFaqClick}
        onStartListening={startListening}
        style={{
          opacity: isActive ? 0 : 1,
          pointerEvents: isActive ? "none" : "all",
          transform: isActive ? "scale(0.95)" : "scale(1)",
        }}
      />

      <ListenOverlay
        state={state}
        transcript={transcript}
        barHeights={barHeights}
        aiResponse={aiResponse}
        speaking={speaking}
        feedbackSent={feedbackSent}
        onStopListening={stopListening}
        onResetToIdle={resetToIdle}
        onFeedback={sendFeedback}
        style={{
          opacity: isActive ? 1 : 0,
          pointerEvents: isActive ? "all" : "none",
          visibility: isActive ? "visible" : "hidden",
        }}
      />
    </div>
  );
}


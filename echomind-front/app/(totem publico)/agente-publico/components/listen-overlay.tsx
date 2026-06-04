"use client";

import type { CSSProperties } from "react";
import { ThumbsDown, ThumbsUp, Volume2, VolumeX, X } from "lucide-react";
import type { ListeningState } from "../types";

type ListenOverlayProps = {
  state: ListeningState;
  transcript: string;
  barHeights: number[];
  aiResponse: string;
  speaking: boolean;
  feedbackSent: boolean;
  onStopListening: () => void;
  onResetToIdle: () => void;
  onFeedback: (helpful: boolean) => void;
  style?: CSSProperties;
};

export function ListenOverlay({
  state,
  transcript,
  barHeights,
  aiResponse,
  speaking,
  feedbackSent,
  onStopListening,
  onResetToIdle,
  onFeedback,
  style,
}: ListenOverlayProps) {
  return (
    <div className="listen-overlay" style={style}>
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
        {state === "listening" && "Ouvindo…"}
        {state === "processing" && "Processando…"}
        {state === "responding" && (speaking ? "Falando…" : "Respondendo…")}
      </p>

      {state === "responding" ? (
        <div className="ai-response-box">
          <p className="ai-response-text">{aiResponse}</p>
          {aiResponse && !feedbackSent && (
            <div className="feedback-row">
              <span>Essa resposta ajudou?</span>
              <button onClick={() => onFeedback(true)}><ThumbsUp size={16} /> Sim</button>
              <button onClick={() => onFeedback(false)}><ThumbsDown size={16} /> Não</button>
            </div>
          )}
          {feedbackSent && <p className="feedback-thanks">Obrigado pelo feedback.</p>}
        </div>
      ) : (
        <p className="listen-transcript">
          {transcript || "..."}
          {state === "listening"} 
        </p>
      )}

      {state === "listening" && (
        <button className="stop-btn" onClick={onStopListening}>
          <X size={14} /> Cancelar
        </button>
      )}

      {state === "responding" && (
        <button className="stop-btn" onClick={onResetToIdle}>
          {speaking ? <VolumeX size={14} /> : <X size={14} />}
          {speaking ? "Parar Áudio" : "Fechar"}
        </button>
      )}
    </div>
  );
}


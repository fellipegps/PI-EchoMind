export type ListeningState = "idle" | "listening" | "processing" | "responding";

export const BAR_COUNT = 12;

export type SpeechRecognitionResultEvent = {
  resultIndex: number;
  results: ArrayLike<{
    0: {
      transcript: string;
    };
  }>;
};

export type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  abort: () => void;
};

export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

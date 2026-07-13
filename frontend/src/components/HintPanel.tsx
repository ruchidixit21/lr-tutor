import { useEffect, useRef, useState } from "react";
import { streamHint } from "../api";

interface Props {
  sessionId: string;
  questionId: string;
  attemptNumber: number;
  disabled: boolean;
}

export default function HintPanel({ sessionId, questionId, attemptNumber, disabled }: Props) {
  const [hints, setHints] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [currentChunk, setCurrentChunk] = useState("");
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    setHints([]);
    setCurrentChunk("");
    setStreaming(false);
    stopRef.current?.();
  }, [questionId]);

  function requestHint() {
    if (streaming) return;
    setStreaming(true);
    setCurrentChunk("");
    stopRef.current = streamHint(
      sessionId,
      questionId,
      attemptNumber,
      (chunk) => setCurrentChunk((prev) => prev + chunk),
      () => {
        setStreaming(false);
        setCurrentChunk((prev) => {
          if (prev) setHints((h) => [...h, prev]);
          return "";
        });
      }
    );
  }

  const hintLabel =
    attemptNumber === 1 ? "Get a hint" : attemptNumber === 2 ? "Get another hint" : "Show answer";

  return (
    <div className="mt-4 space-y-3">
      {hints.map((h, i) => (
        <div key={i} className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-gray-800 whitespace-pre-wrap">
          <span className="font-semibold text-amber-700">Hint {i + 1}: </span>
          {h}
        </div>
      ))}
      {currentChunk && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-gray-800 whitespace-pre-wrap">
          <span className="font-semibold text-amber-700">Hint {hints.length + 1}: </span>
          {currentChunk}
          <span className="animate-pulse">▋</span>
        </div>
      )}
      {!disabled && hints.length < 3 && !streaming && (
        <button
          onClick={requestHint}
          className="text-sm px-4 py-1.5 rounded border border-amber-400 text-amber-700 hover:bg-amber-50 transition-colors"
        >
          {hintLabel}
        </button>
      )}
    </div>
  );
}

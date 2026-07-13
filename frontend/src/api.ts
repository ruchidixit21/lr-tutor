const BASE = "http://localhost:8000";

export interface AnswerChoice {
  label: string;
  text: string;
}

export interface QuestionData {
  question_id: string;
  question_type: string;
  stimulus: string;
  stem: string;
  choices: AnswerChoice[];
}

export interface SessionResponse {
  session_id: string;
  message: string;
  question: QuestionData | null;
  weakness_scores: Record<string, number> | null;
}

export async function createSession(): Promise<SessionResponse> {
  const res = await fetch(`${BASE}/session`, { method: "POST" });
  if (!res.ok) throw new Error(`createSession failed: ${res.status}`);
  return res.json();
}

export async function sendMessage(
  sessionId: string,
  message: string
): Promise<SessionResponse> {
  const res = await fetch(`${BASE}/session/${sessionId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`sendMessage failed: ${res.status}`);
  return res.json();
}

export function streamHint(
  sessionId: string,
  questionId: string,
  attemptNumber: number,
  onChunk: (text: string) => void,
  onDone: () => void
): () => void {
  const url = `${BASE}/session/${sessionId}/hint-stream?question_id=${encodeURIComponent(questionId)}&attempt_number=${attemptNumber}`;
  const es = new EventSource(url);
  es.onmessage = (e) => {
    if (e.data === "[DONE]") {
      es.close();
      onDone();
    } else {
      onChunk(e.data);
    }
  };
  es.onerror = () => {
    es.close();
    onDone();
  };
  return () => es.close();
}

export async function submitHumanScore(payload: {
  question_id: string;
  logical_validity: number;
  answer_uniqueness: number;
  distractor_quality: number;
  type_accuracy: number;
  stimulus_independence: number;
  notes?: string;
}): Promise<void> {
  const res = await fetch(`${BASE}/human-score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`submitHumanScore failed: ${res.status}`);
}

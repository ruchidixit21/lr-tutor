import { useState } from "react";
import { QuestionData, createSession, sendMessage } from "./api";
import AnswerSelector from "./components/AnswerSelector";
import HintPanel from "./components/HintPanel";
import HumanEvalPanel from "./components/HumanEvalPanel";
import Markdown from "./components/Markdown";
import Question from "./components/Question";
import WeaknessHeatmap from "./components/WeaknessHeatmap";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [agentMessage, setAgentMessage] = useState("");
  const [currentQuestion, setCurrentQuestion] = useState<QuestionData | null>(null);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [questionResolved, setQuestionResolved] = useState(false);
  const [evalSubmitted, setEvalSubmitted] = useState(false);
  const [weaknessScores, setWeaknessScores] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);

  async function start() {
    setLoading(true);
    try {
      const res = await createSession();
      setSessionId(res.session_id);
      setAgentMessage(res.message);
      if (res.question) loadQuestion(res.question);
      if (res.weakness_scores) setWeaknessScores(res.weakness_scores);
    } finally {
      setLoading(false);
    }
  }

  function loadQuestion(q: QuestionData) {
    setCurrentQuestion(q);
    setSelectedAnswer(null);
    setSubmitted(false);
    setAttempts(0);
    setQuestionResolved(false);
    setEvalSubmitted(false);
  }

  async function submitAnswer() {
    if (!sessionId || !selectedAnswer || !currentQuestion) return;
    setSubmitted(true);
    setAttempts((a) => a + 1);
    setLoading(true);
    try {
      const res = await sendMessage(sessionId, `My answer is ${selectedAnswer}`);
      setAgentMessage(res.message);
      if (res.question && res.question.question_id !== currentQuestion.question_id) {
        loadQuestion(res.question);
      }
      if (res.weakness_scores) setWeaknessScores(res.weakness_scores);
      if (/correct|well done|that'?s right|the answer is/i.test(res.message)) {
        setQuestionResolved(true);
      }
    } finally {
      setLoading(false);
    }
  }

  if (!sessionId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <h1 className="text-3xl font-bold text-gray-900">LSAT Tutor</h1>
          <p className="text-gray-500 max-w-sm">
            Adaptive Logical Reasoning practice with Socratic hints
          </p>
          <button
            onClick={start}
            disabled={loading}
            className="px-8 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Starting…" : "Start session"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sticky sidebar */}
      <aside className="w-64 shrink-0">
        <div className="sticky top-0 h-screen overflow-y-auto bg-white border-r border-gray-200 p-4">
          <h2 className="text-sm font-bold text-gray-900 mb-4">LSAT Tutor</h2>
          <WeaknessHeatmap scores={weaknessScores} />
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 max-w-2xl mx-auto py-8 px-6 space-y-4">
        {/* Agent message */}
        {agentMessage && (
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            {loading ? (
              <p className="text-sm text-gray-400 animate-pulse">Thinking…</p>
            ) : (
              <Markdown text={agentMessage} />
            )}
          </div>
        )}

        {/* Question block */}
        {currentQuestion && (
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
            <Question
              questionType={currentQuestion.question_type}
              stimulus={currentQuestion.stimulus}
              stem={currentQuestion.stem}
              choices={currentQuestion.choices}
              selectedAnswer={selectedAnswer}
              onSelect={setSelectedAnswer}
              submitted={submitted}
            />
            <AnswerSelector
              selectedAnswer={selectedAnswer}
              submitted={submitted}
              onSubmit={submitAnswer}
            />
            {submitted && sessionId && (
              <HintPanel
                sessionId={sessionId}
                questionId={currentQuestion.question_id}
                attemptNumber={Math.min(attempts, 3)}
                disabled={!submitted}
              />
            )}
            {questionResolved && !evalSubmitted && (
              <HumanEvalPanel
                questionId={currentQuestion.question_id}
                onSubmitted={() => setEvalSubmitted(true)}
              />
            )}
          </div>
        )}
      </main>
    </div>
  );
}

import { useState } from "react";
import { submitHumanScore } from "../api";

interface Props {
  questionId: string;
  onSubmitted: () => void;
}

const DIMS = [
  { key: "logical_validity", label: "Logical validity" },
  { key: "answer_uniqueness", label: "Answer uniqueness" },
  { key: "distractor_quality", label: "Distractor quality" },
  { key: "type_accuracy", label: "Type accuracy" },
  { key: "stimulus_independence", label: "Stimulus independence" },
] as const;

type DimKey = (typeof DIMS)[number]["key"];

export default function HumanEvalPanel({ questionId, onSubmitted }: Props) {
  const [scores, setScores] = useState<Record<DimKey, number>>({
    logical_validity: 3,
    answer_uniqueness: 3,
    distractor_quality: 3,
    type_accuracy: 3,
    stimulus_independence: 3,
  });
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSubmit() {
    setSaving(true);
    try {
      await submitHumanScore({ question_id: questionId, ...scores, notes });
      setSaved(true);
      onSubmitted();
    } finally {
      setSaving(false);
    }
  }

  if (saved) {
    return <p className="text-sm text-green-600 font-medium">Rating saved.</p>;
  }

  return (
    <div className="border border-gray-200 rounded-xl p-4 space-y-3 bg-gray-50">
      <h3 className="text-sm font-semibold text-gray-700">Rate this question (1–5)</h3>
      {DIMS.map(({ key, label }) => (
        <div key={key} className="flex items-center gap-3">
          <span className="text-sm text-gray-600 w-48 shrink-0">{label}</span>
          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={scores[key]}
            onChange={(e) =>
              setScores((s) => ({ ...s, [key]: Number(e.target.value) }))
            }
            className="flex-1 accent-indigo-600"
          />
          <span className="text-sm font-medium text-gray-800 w-4">{scores[key]}</span>
        </div>
      ))}
      <input
        type="text"
        placeholder="Notes (optional)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
      />
      <button
        onClick={handleSubmit}
        disabled={saving}
        className="px-4 py-1.5 bg-indigo-600 text-white rounded text-sm font-medium disabled:opacity-50 hover:bg-indigo-700 transition-colors"
      >
        {saving ? "Saving…" : "Submit rating"}
      </button>
    </div>
  );
}

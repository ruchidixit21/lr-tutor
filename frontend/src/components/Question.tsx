import { AnswerChoice } from "../api";

interface Props {
  questionType: string;
  stimulus: string;
  stem: string;
  choices: AnswerChoice[];
  selectedAnswer: string | null;
  onSelect: (label: string) => void;
  submitted: boolean;
}

export default function Question({
  questionType,
  stimulus,
  stem,
  choices,
  selectedAnswer,
  onSelect,
  submitted,
}: Props) {
  return (
    <div className="space-y-4">
      <div className="text-xs font-semibold uppercase tracking-widest text-indigo-600">
        {questionType.replace(/_/g, " ")}
      </div>
      <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">{stimulus}</p>
      <p className="font-medium text-gray-900">{stem}</p>
      <ul className="space-y-2">
        {choices.map((c) => {
          const inputId = `choice-${c.label}`;
          const isSelected = selectedAnswer === c.label;
          return (
            <li key={c.label}>
              <label
                htmlFor={inputId}
                className={[
                  "flex items-start gap-3 p-3 rounded-lg border transition-colors",
                  submitted ? "opacity-60 cursor-default" : "cursor-pointer hover:bg-indigo-50 hover:border-indigo-300",
                  isSelected ? "bg-indigo-50 border-indigo-400" : "border-gray-200 bg-white",
                ].join(" ")}
              >
                <input
                  id={inputId}
                  type="radio"
                  name="answer"
                  value={c.label}
                  checked={isSelected}
                  onChange={() => onSelect(c.label)}
                  disabled={submitted}
                  className="mt-0.5 accent-indigo-600 shrink-0"
                />
                <span className="text-gray-800">
                  <span className="font-semibold mr-1">{c.label}.</span>
                  {c.text}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

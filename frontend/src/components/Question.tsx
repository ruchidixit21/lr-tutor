import { AnswerChoice } from "../api";

interface Props {
  questionType: string;
  stimulus: string;
  stem: string;
  choices: AnswerChoice[];
  selectedAnswer: string | null;
  onSelect: (label: string) => void;
  submitted: boolean;
  wrongAnswers: string[];
  resolvedAnswer: string | null;
}

export default function Question({
  questionType,
  stimulus,
  stem,
  choices,
  selectedAnswer,
  onSelect,
  submitted,
  wrongAnswers,
  resolvedAnswer,
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
          const isWrong = wrongAnswers.includes(c.label);
          const isCorrect = resolvedAnswer === c.label;
          const isDisabled = submitted || isWrong || resolvedAnswer !== null;

          let labelClass = "flex items-start gap-3 p-3 rounded-lg border transition-colors ";
          if (isCorrect) {
            labelClass += "bg-green-50 border-green-500 cursor-default";
          } else if (isWrong) {
            labelClass += "bg-red-50 border-red-400 opacity-60 cursor-default";
          } else if (isDisabled) {
            labelClass += "opacity-60 cursor-default " + (isSelected ? "bg-indigo-50 border-indigo-400" : "border-gray-200 bg-white");
          } else {
            labelClass += isSelected
              ? "bg-indigo-50 border-indigo-400 cursor-pointer"
              : "border-gray-200 bg-white cursor-pointer hover:bg-indigo-50 hover:border-indigo-300";
          }

          return (
            <li key={c.label}>
              <label htmlFor={inputId} className={labelClass}>
                <input
                  id={inputId}
                  type="radio"
                  name="answer"
                  value={c.label}
                  checked={isSelected}
                  onChange={() => onSelect(c.label)}
                  disabled={isDisabled}
                  className="mt-0.5 shrink-0 accent-indigo-600"
                />
                <span className={isCorrect ? "text-green-800 font-medium" : isWrong ? "text-red-700" : "text-gray-800"}>
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

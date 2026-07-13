interface Props {
  selectedAnswer: string | null;
  submitted: boolean;
  onSubmit: () => void;
}

export default function AnswerSelector({ selectedAnswer, submitted, onSubmit }: Props) {
  if (submitted) return null;
  return (
    <button
      onClick={onSubmit}
      disabled={!selectedAnswer}
      className="mt-4 px-6 py-2 rounded-lg bg-indigo-600 text-white font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-indigo-700 transition-colors"
    >
      Submit answer
    </button>
  );
}

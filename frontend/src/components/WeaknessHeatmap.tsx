interface Props {
  scores: Record<string, number>;
}

const QUESTION_TYPES = [
  "assumption_necessary",
  "assumption_sufficient",
  "strengthen",
  "weaken",
  "flaw",
  "inference",
  "must_be_true",
  "cannot_be_true",
  "paradox",
  "parallel_reasoning",
  "parallel_flaw",
  "point_of_disagreement",
  "evaluate",
  "principle_identify",
  "principle_apply",
];

function scoreToColor(score: number): string {
  // 0.0 = weak (red), 1.0 = strong (green)
  const r = Math.round(239 - score * (239 - 34));
  const g = Math.round(68 + score * (197 - 68));
  const b = Math.round(68 + score * (94 - 68));
  return `rgb(${r},${g},${b})`;
}

export default function WeaknessHeatmap({ scores }: Props) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Weakness profile
      </h3>
      <div className="grid grid-cols-3 gap-1.5">
        {QUESTION_TYPES.map((qt) => {
          const score = scores[qt] ?? 0.5;
          return (
            <div
              key={qt}
              title={`${qt.replace(/_/g, " ")}: ${(score * 100).toFixed(0)}%`}
              className="rounded p-1.5 text-center"
              style={{ backgroundColor: scoreToColor(score) }}
            >
              <span className="text-white text-xs font-medium leading-tight block">
                {qt.replace(/_/g, " ")}
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-gray-400 mt-1">Red = weak, green = strong</p>
    </div>
  );
}

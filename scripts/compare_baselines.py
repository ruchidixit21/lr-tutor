"""Compare RAG-grounded vs. naive baseline question quality.

Loads rubric scores from both conditions, computes mean ± std per dimension,
runs two-sample t-tests, prints a table, and saves a bar chart to
eval/baseline_comparison.png.

Usage:
    uv run scripts/compare_baselines.py
    uv run scripts/compare_baselines.py \
        --rag eval/generated_samples.jsonl \
        --naive eval/naive_scores.jsonl \
        --out eval/baseline_comparison.png
"""
import argparse
import json
from pathlib import Path

DIMENSIONS = [
    "logical_validity",
    "answer_uniqueness",
    "distractor_quality",
    "type_accuracy",
    "stimulus_independence",
]


def load_scores(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def column(rows: list[dict], dim: str) -> list[float]:
    return [r[dim] for r in rows if dim in r]


def run(rag_path: Path, naive_path: Path, out: Path) -> None:
    try:
        import numpy as np
        from scipy import stats
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        raise SystemExit(
            "Missing dependencies. Run: uv add numpy scipy matplotlib"
        )

    rag = load_scores(rag_path)
    naive = load_scores(naive_path)

    if not rag:
        raise SystemExit(f"No scores found in {rag_path}")
    if not naive:
        raise SystemExit(f"No scores found in {naive_path}")

    print(f"\nRAG questions:   {len(rag)}")
    print(f"Naive questions: {len(naive)}")
    print()

    # --- Table ---------------------------------------------------------------
    header = f"{'Dimension':<26}  {'RAG mean':>9}  {'Naive mean':>10}  {'Delta':>7}  {'p-value':>9}"
    print(header)
    print("-" * len(header))

    rag_means, naive_means, deltas, pvals = [], [], [], []

    for dim in DIMENSIONS:
        r = np.array(column(rag, dim), dtype=float)
        n = np.array(column(naive, dim), dtype=float)
        delta = r.mean() - n.mean()
        _, p = stats.ttest_ind(r, n, equal_var=False)
        sig = "**" if p < 0.01 else ("*" if p < 0.05 else "")
        print(
            f"{dim:<26}  {r.mean():>7.2f}±{r.std():.2f}  "
            f"{n.mean():>8.2f}±{n.std():.2f}  "
            f"{delta:>+7.2f}  {p:>9.4f}{sig}"
        )
        rag_means.append(r.mean())
        naive_means.append(n.mean())
        deltas.append(delta)
        pvals.append(p)

    # Overall average
    rag_all = np.array([r[d] for r in rag for d in DIMENSIONS if d in r], dtype=float)
    naive_all = np.array([r[d] for r in naive for d in DIMENSIONS if d in r], dtype=float)
    rag_avg = np.array([sum(r[d] for d in DIMENSIONS) / len(DIMENSIONS) for r in rag], dtype=float)
    naive_avg = np.array([sum(r[d] for d in DIMENSIONS) / len(DIMENSIONS) for r in naive], dtype=float)
    _, p_avg = stats.ttest_ind(rag_avg, naive_avg, equal_var=False)
    delta_avg = rag_avg.mean() - naive_avg.mean()
    sig = "**" if p_avg < 0.01 else ("*" if p_avg < 0.05 else "")
    print("-" * len(header))
    print(
        f"{'AVERAGE':<26}  {rag_avg.mean():>7.2f}±{rag_avg.std():.2f}  "
        f"{naive_avg.mean():>8.2f}±{naive_avg.std():.2f}  "
        f"{delta_avg:>+7.2f}  {p_avg:>9.4f}{sig}"
    )
    print("\n* p<0.05   ** p<0.01")

    # --- Bar chart -----------------------------------------------------------
    x = np.arange(len(DIMENSIONS))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    bars_rag = ax.bar(x - width / 2, rag_means, width, label="RAG-grounded", color="#4f46e5")
    bars_naive = ax.bar(x + width / 2, naive_means, width, label="Naïve baseline", color="#e5793c")

    # Significance stars
    for i, (rm, nm, p) in enumerate(zip(rag_means, naive_means, pvals)):
        if p < 0.05:
            star = "**" if p < 0.01 else "*"
            y = max(rm, nm) + 0.1
            ax.text(x[i], y, star, ha="center", va="bottom", fontsize=11, color="#111")

    short_labels = [d.replace("_", "\n") for d in DIMENSIONS]
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=9)
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("Rubric score (1–5)")
    ax.set_title(
        f"RAG-grounded vs. Naïve baseline  "
        f"(n={len(rag)} vs {len(naive)},  Δavg={delta_avg:+.2f})"
    )
    ax.legend()
    ax.axhline(3.5, color="gray", linestyle="--", linewidth=0.8, alpha=0.6, label="Quality floor (3.5)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"\nChart saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--rag", type=Path, default=Path("eval/generated_samples.jsonl"))
    parser.add_argument("--naive", type=Path, default=Path("eval/naive_scores.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("eval/baseline_comparison.png"))
    args = parser.parse_args()
    run(args.rag, args.naive, args.out)

"""Compute novelty scores for generated questions and plot validity vs. novelty.

Novelty = cosine distance from a generated question to its nearest real LSAT
question in embedding space. Higher distance = more novel (less paraphrase).

"Valid and novel" zone: rubric average ≥ 3.5 AND novelty distance ≥ 0.25.
This is the primary README chart claimed in the Phase 4 spec.

Usage:
    uv run scripts/compute_novelty.py
    uv run scripts/compute_novelty.py --scored-file eval/generated_samples.jsonl --out novelty.png
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Add project root to path so src imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.db import get_collection
from src.models import QuestionSource


def _get_embeddings_by_source(
    collection,
) -> tuple[np.ndarray, list[str], np.ndarray, list[str]]:
    """Fetch all embeddings from Chroma, split into real vs. generated."""
    result = collection.get(include=["embeddings", "metadatas"])
    embeddings = np.array(result["embeddings"], dtype=np.float32)
    ids = result["ids"]
    metadatas = result["metadatas"]

    real_idx = [i for i, m in enumerate(metadatas) if m.get("source") == QuestionSource.REAL_LSAT.value]
    gen_idx = [i for i, m in enumerate(metadatas) if m.get("source") == QuestionSource.GENERATED.value]

    real_embs = embeddings[real_idx]
    real_ids = [ids[i] for i in real_idx]
    gen_embs = embeddings[gen_idx]
    gen_ids = [ids[i] for i in gen_idx]

    return real_embs, real_ids, gen_embs, gen_ids


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance between two vectors (1 - cosine similarity)."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - np.dot(a, b) / (norm_a * norm_b))


def nearest_real_distance(gen_emb: np.ndarray, real_embs: np.ndarray) -> float:
    """Minimum cosine distance from a generated embedding to any real LSAT embedding."""
    distances = [_cosine_distance(gen_emb, r) for r in real_embs]
    return min(distances)


def load_rubric_scores(scored_file: Path) -> dict[str, float]:
    """Load question_id → average rubric score from a JSONL of scored questions.

    Each line should have: {"question": {...}, "score": {rubric fields...}}
    or just rubric fields with a "question_id" key.
    """
    scores: dict[str, float] = {}
    if not scored_file.exists():
        return scores
    with scored_file.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            # Support both {question_id, ...rubric...} and {question: {...}, score: {...}}
            if "score" in obj and "question" in obj:
                qid = obj["question"]["id"]
                s = obj["score"]
            else:
                qid = obj.get("question_id", "")
                s = obj
            dims = [
                s.get("logical_validity", 0),
                s.get("answer_uniqueness", 0),
                s.get("distractor_quality", 0),
                s.get("type_accuracy", 0),
                s.get("stimulus_independence", 0),
            ]
            if all(d > 0 for d in dims):
                scores[qid] = sum(dims) / len(dims)
    return scores


def compute_and_plot(scored_file: Path, out: Path, show: bool) -> None:
    collection = get_collection()

    real_embs, real_ids, gen_embs, gen_ids = _get_embeddings_by_source(collection)
    print(f"Corpus: {len(real_ids)} real LSAT, {len(gen_ids)} generated")

    if not len(real_embs):
        print("No real LSAT embeddings found in Chroma. Load corpus first.")
        sys.exit(1)
    if not len(gen_embs):
        print("No generated question embeddings found in Chroma.")
        sys.exit(1)

    # Compute novelty (cosine distance to nearest real question) for each generated question
    novelty_scores = {
        gen_ids[i]: nearest_real_distance(gen_embs[i], real_embs)
        for i in range(len(gen_ids))
    }

    rubric_scores = load_rubric_scores(scored_file)

    # Intersect: only questions with both novelty and rubric scores
    common_ids = [qid for qid in gen_ids if qid in rubric_scores]
    if not common_ids:
        print(
            f"No generated questions found with rubric scores in {scored_file}.\n"
            "Run scripts/run_eval.py first to score generated questions."
        )
        sys.exit(1)

    novelty = np.array([novelty_scores[qid] for qid in common_ids])
    rubric = np.array([rubric_scores[qid] for qid in common_ids])

    # Valid+novel zone thresholds
    RUBRIC_FLOOR = 3.5
    NOVELTY_FLOOR = 0.25

    in_zone = (rubric >= RUBRIC_FLOOR) & (novelty >= NOVELTY_FLOOR)
    pct_in_zone = in_zone.sum() / len(in_zone) * 100

    print(f"\nNovelty stats (cosine distance to nearest real LSAT):")
    print(f"  mean={novelty.mean():.3f}  min={novelty.min():.3f}  max={novelty.max():.3f}")
    print(f"\nRubric avg stats:")
    print(f"  mean={rubric.mean():.2f}  min={rubric.min():.2f}  max={rubric.max():.2f}")
    print(f"\nValid+novel zone (rubric≥{RUBRIC_FLOOR}, novelty≥{NOVELTY_FLOOR}):")
    print(f"  {in_zone.sum()}/{len(in_zone)} questions = {pct_in_zone:.1f}%")

    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    fig, ax = plt.subplots(figsize=(8, 6))

    colors = ["#2196F3" if z else "#FF7043" for z in in_zone]
    ax.scatter(novelty, rubric, c=colors, alpha=0.75, edgecolors="white", linewidths=0.5, s=80)

    # Draw zone boundaries
    ax.axvline(x=NOVELTY_FLOOR, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(y=RUBRIC_FLOOR, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)

    # Shade valid+novel quadrant
    ax.axvspan(NOVELTY_FLOOR, ax.get_xlim()[1] if ax.get_xlim()[1] > NOVELTY_FLOOR else 1.0,
               ymin=(RUBRIC_FLOOR - 1) / 4, ymax=1.0, alpha=0.05, color="#2196F3")

    ax.set_xlabel("Novelty (cosine distance to nearest real LSAT question)", fontsize=11)
    ax.set_ylabel("Rubric average (1–5)", fontsize=11)
    ax.set_title(f"Generated questions: validity vs. novelty\n"
                 f"{pct_in_zone:.1f}% in valid+novel zone ({in_zone.sum()}/{len(in_zone)})", fontsize=12)
    ax.set_ylim(1, 5.2)
    ax.set_xlim(left=0)

    in_zone_patch = mpatches.Patch(color="#2196F3", label=f"Valid+novel ({in_zone.sum()})")
    out_zone_patch = mpatches.Patch(color="#FF7043", label=f"Below threshold ({(~in_zone).sum()})")
    ax.legend(handles=[in_zone_patch, out_zone_patch], loc="lower right")

    plt.tight_layout()
    plt.savefig(out, dpi=150)
    print(f"\nPlot saved to {out}")
    if show:
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute novelty scores and plot validity vs. novelty.")
    parser.add_argument(
        "--scored-file",
        type=Path,
        default=Path("eval/generated_samples.jsonl"),
        help="JSONL file with scored generated questions (default: eval/generated_samples.jsonl)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("eval/novelty_plot.png"),
        help="Output path for the scatter plot PNG (default: eval/novelty_plot.png)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open the plot in a window after saving",
    )
    args = parser.parse_args()
    compute_and_plot(args.scored_file, args.out, args.show)

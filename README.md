# LSAT Logical Reasoning Tutor

An agentic tutoring system that generates high-quality LSAT Logical Reasoning questions using RAG, evaluates them with a scored rubric, and adapts to student weaknesses via a Socratic tutoring loop.

---

## Problem

LLMs generate poor LSAT questions because they pattern-match on surface structure — question wording, answer phrasing — rather than reasoning structure: what logical gap is being tested, whether exactly one answer is defensible. This project directly addresses that failure mode.

## Architecture

Three interlocking components:

**1. RAG-grounded generation**
A corpus of real LSAT questions is embedded by `stimulus + stem` (not stimulus alone — the reasoning structure lives in their relationship). At generation time, the k=3 most similar real questions are retrieved and used as grounding context. This anchors generation to expert-authored reasoning patterns rather than surface imitation.

**2. Evaluation rubric**
A five-dimension rubric scores each generated question: logical validity, answer uniqueness, distractor quality, type accuracy, and stimulus independence (1–5 each). The rubric is calibrated against real LSAT questions (ceiling ≥4.0). A gated generator produces 5 candidates and returns the highest-scoring one, discarding questions that score below 3.5.

**3. Agentic Socratic tutor**
A Claude-powered agent tracks per-type accuracy with exponential recency decay, biases question selection toward weak types, and gives Socratic hints rather than revealing answers. All tool calls are traced in LangSmith. The agent loop uses four tools: `get_next_question`, `submit_answer`, `get_hint`, `get_weakness_report`.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| Frontend | React 18, TypeScript, Vite, Tailwind |
| LLM | Anthropic Claude (`claude-sonnet-4-6`) |
| Vector store | Chroma (cosine similarity, `stimulus + stem` embeddings) |
| Validation | Pydantic v2 |
| Tracing | LangSmith |
| Testing | pytest |

## Project status

| Phase | Status |
|---|---|
| Phase 1 — Corpus ingestion + RAG retrieval | ✅ Complete |
| Phase 2 — Generation + rubric scorer | 🔄 In progress |
| Phase 3 — Agentic tutor loop | ⏳ Planned |
| Phase 4 — Quality gate + novelty metric | ⏳ Planned |
| Phase 5 — React frontend + human eval | ⏳ Planned |

**Corpus:** 101 real LSAT questions (PrepTest 140, 4 LR sections) with correct answers, embedded in Chroma. 9 of 15 question types have ≥5 examples; remaining types filled with generated questions validated by the rubric scorer.

## Setup

```bash
uv sync --extra dev
cp .env.example .env   # add ANTHROPIC_API_KEY
uv run pytest
uv run uvicorn src.api:app --reload
```

## Key design decisions

**Why embed `stimulus + stem` together:** the reasoning structure lives in the relationship between the two — embedding the stimulus alone retrieves by topic, not by the type of logical move being tested.

**Why generate N candidates and gate by rubric score:** single-shot generation produces variable quality. Generate-then-self-critique is a meaningful agentic pattern; the quality gate ensures the tutor never delivers a logically broken question.

**Why recency-weighted accuracy for weakness tracking:** simple accuracy doesn't reflect learning. A student who got the first 5 wrong but the last 5 right is strong, not 50%. Exponential decay weights recent attempts more heavily.

**Why automated rubric + human validation:** reporting Pearson r between automated and human scores turns "I built an eval" into "I built and validated an eval" — the methodological claim that makes the project credible.

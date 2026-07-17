# Dev Log

## 2026-06-11 — Session 1: Project scaffold

**Built:**
- Full directory structure per CLAUDE.md spec
- `pyproject.toml` with all Phase 1–3 dependencies
- `src/models.py` — complete Pydantic data model (single source of truth)
- `src/db.py` — Chroma client setup (PersistentClient, cosine similarity)
- Stubs for all remaining `src/` modules with `NotImplementedError`
- `src/tools.py` — complete tool schemas for the agentic loop (Phase 3)
- `src/api.py` — minimal FastAPI app with `/health` route
- All `scripts/` with argparse shells
- `tests/test_models.py` — model validation and roundtrip tests

**Architectural decisions:**
- Chroma over pgvector: corpus is small (≤200 questions), no SQL joins needed, zero-config
- Corpus sourcing limited to LSAC free official materials (~50 real questions); remaining types filled with verified generated questions
- Model: `claude-sonnet-4-6` throughout

**Next:** copy `.env.example` → `.env`, add API key, run `uv sync`, run `pytest` to verify models pass.

---

## 2026-06-14 to 2026-06-20 — Sessions 2–4: Phase 1 corpus ingestion

**Built:**
- `scripts/scrape_lawhub.py` — Playwright-based scraper for LawHub (LSAC's online test platform). Navigates through questions in section-review mode (after completing a section, correct answers are shown), extracts page text, sends to Claude text API for structured parsing. Non-headless browser avoids LawHub's JS-based DevTools detection. Auth state saved to `.lawhub_auth.json` (gitignored).
- `scripts/pdf_to_images.py` — PDF-to-JPEG converter using pymupdf, for future scan-based extraction
- `scripts/load_vectors.py` — upserts corpus JSONL into Chroma with `question_type` and `source` as filterable metadata fields
- `src/retriever.py` — semantic search with optional type filter via Chroma `where` clause
- `src/api.py` — added `GET /retrieve?q=...&type=...&k=5` endpoint
- `eval/retrieval_cases.json` — 10 hand-written retrieval eval cases
- `tests/fixtures/mini_corpus.jsonl` + `tests/test_retriever.py` — retrieval tests using ephemeral Chroma (no disk I/O)

**Corpus status:**
- 101 real LSAT questions scraped from PrepTest 140 (4 LR sections), all with correct answers
- 9 of 15 question types have ≥5 examples; 6 need generated fill-ins (must_be_true: 1, parallel_flaw: 4, point_of_disagreement: 4, principle_identify: 2, cannot_be_true: 0, evaluate: 0)

**Issues fixed:**
- `onnxruntime==1.27.0` has no macOS x86_64 (Intel Mac) wheel — pinned to `<=1.20.1` via `[tool.uv] override-dependencies`
- `chromadb.Client` is a factory function in newer chromadb, not a class — changed type annotation to `chromadb.api.ClientAPI`
- LawHub's Next button detection was fragile — added 5-selector fallback cascade with debug logging

**Architectural decisions:**
- Scraped in section-review mode (not exam mode) so correct answers are captured in one pass
- Text extraction + Claude text API is cheaper and more accurate than vision API for this layout
- `source_detail` format: `"PrepTest 140 Section N QM"` for traceability back to source

**Next:** Phase 2 — implement generator, scorer, and generate ~5 fill-in questions for the 6 weak types.

---

## 2026-06-20 to 2026-06-21 — Session 5: Phase 2 generation + scoring

**Built:**
- `src/generator.py` — RAG-grounded single-candidate generation. Retrieves k=3 real LSAT examples of the target type, pairs them with per-type structural instructions (15 detailed instruction strings), prompts claude-sonnet-4-6 to generate a novel question. Forces `question_type` to the correct enum value post-parse to handle Claude's occasional uppercase/spaced output.
- `src/scorer.py` — five-dimension rubric scorer (logical_validity, answer_uniqueness, distractor_quality, type_accuracy, stimulus_independence, each 1–5). System prompt calibrated so real LSAT questions should average ≥4.0.
- `src/api.py` — added `POST /generate` and `POST /score` endpoints.
- `scripts/run_eval.py` — batch scorer with per-dimension summary table.
- `scripts/generate_fillin.py` — fills corpus gaps by type, rejects questions below configurable score threshold (default 3.5). Retries up to `attempts × needed` times per type.

**Corpus completion:**
- Generated 19 fill-in questions across 6 weak types in two runs
- Generated question scores: avg 4.2–4.8 across saved questions (all above 3.5 threshold)
- Final corpus: 120 questions (101 real LSAT + 19 generated), all 15 types with ≥5 examples
- Loaded into Chroma: 120 documents

**Issues fixed:**
- Claude outputting `"CANNOT BE TRUE"` / `"EVALUATE"` instead of snake_case enum values — fixed by (1) adding explicit enum value to prompt and (2) overriding `question_type` in parsed JSON before Pydantic validation
- Occasional empty scorer responses — intermittent API issue, handled by existing retry logic in generate_fillin.py
- `max_tokens=1024` too low for generation — raised to 2048

**Next:** Phase 3 — agentic tutor loop (WeaknessTracker, tool handlers, agent system prompt, LangSmith tracing).

---

## 2026-06-21 — Session 6: Phase 3 agentic tutor loop

**Built:**
- `src/weakness.py` — WeaknessTracker with exponential recency decay (decay=0.85, 2x boost for last 10 attempts). `select_type()` samples by weakness weight (1 - score), floored at 0.05 so all types stay reachable. `get_weakest_types(n=3)` for reporting.
- `prompts/agent_system_prompt.txt` — Socratic tutor system prompt (user-authored + approved). Covers: Socratic method, 2-attempt rule, 3-level hint progression, 4 wrong-answer pattern diagnostics, tone guidelines, session flow, tool use rules, hard constraints.
- `src/agent.py` — TutorSession class with tool dispatch and Claude tool-use loop:
  - Tool handlers: `get_next_question` (calls `generate()`, sets `current_question`), `submit_answer` (checks answer, records to WeaknessTracker), `get_hint` (calls claude-sonnet-4-6 with separate hint system prompt, calibrated by attempt_number 1–3), `get_weakness_report` (returns WeaknessModel + weakest 3 types)
  - `run_turn()` drives the tool-use loop: appends user message → calls Claude → executes tool calls → feeds results back → repeats until `end_turn`
  - Separate `_HINT_SYSTEM` prompt: Hint 1 indirect/guiding question, Hint 2 direct/structural, Hint 3 reveal + full explanation
- `src/api.py` — added Phase 3 session endpoints:
  - `POST /session` — creates TutorSession, sends opening message, returns `session_id`
  - `POST /session/{id}/message` — routes user message through `run_turn()`, returns agent reply
  - In-memory `_sessions` dict (sufficient for demo; replace with persistent store for production)
- `tests/test_agent.py` — 7 offline unit tests for tool dispatch logic (all mocked, no API calls, fast)

**Architectural decisions:**
- Hint generation uses a separate Claude call with a dedicated `_HINT_SYSTEM` prompt rather than letting the main agent call a tool. This ensures hint quality is controlled independently of the agent's conversational reasoning — the agent calls `get_hint`, which itself calls Claude. The tradeoff is an extra API call per hint, which is acceptable.
- Sessions are held in-memory (dict on the FastAPI process). This is fine for a demo with one user. For a multi-user deployment, sessions would need a persistent store (Redis/DB) keyed by session_id.
- LangSmith `@traceable` decorator is wired in but requires LANGSMITH_API_KEY to activate. Tests run without it.

**All 11 tests passing** (test_agent.py × 7, test_models.py × 4).

**Next:** Phase 4 — gated generator (generate 5, score, return best) + novelty metric + scatter plot.

---

## 2026-06-22 — Session 7: Phase 4 gated generator + novelty metric

**Built:**
- `src/generator_gated.py` — `generate_gated(question_type, candidates=5, quality_floor=3.5, max_retries=2)`: generates N candidates sequentially, scores each with the rubric scorer, returns `(Question, RubricScore)` for the highest-scoring one. If best average is below `quality_floor`, retries the full slate up to `max_retries` times. Returns the best seen across all attempts regardless — only raises `RuntimeError` if every API call fails outright.
- `scripts/compute_novelty.py` — fetches all embeddings directly from Chroma (no re-embedding), splits by source (`real_lsat` vs `generated`), computes cosine distance from each generated question to its nearest real LSAT neighbor, loads rubric averages from a scored JSONL file, prints summary stats, and saves a scatter plot (x=novelty, y=rubric avg) with valid+novel zone highlighted. Valid+novel thresholds: rubric ≥ 3.5, novelty ≥ 0.25.
- Added `matplotlib` and `numpy` to dependencies via `uv add`.
- `tests/test_generator_gated.py` — 4 unit tests (all mocked): best-selection, retry-on-low-score, early-exit-on-floor-met, raise-on-total-failure.

**All 4 tests passing.**

**Validation result:** 30/30 gated-generated questions (100%) landed in the valid+novel zone (rubric ≥3.5, novelty ≥0.25). Phase 4 criterion was ≥70% — well exceeded.

**Issues fixed along the way:**
- Scorer intermittently returned prose analysis instead of JSON (despite system prompt). Fix: extract JSON object by finding first `{` and last `}` in response, regardless of surrounding text.
- Assistant prefill (`{"role": "assistant", "content": "{"}`) was attempted but `claude-sonnet-4-6` rejects it with 400. Reverted to JSON extraction approach.
- One generator candidate produced truncated JSON (same root cause); applied the same extraction fix to `generator.py`.
- Scorer retry logic added: exponential backoff (2s, 4s) between retries, max 3 attempts.

**Next:** Phase 5 — React frontend, SSE streaming hints, WeaknessHeatmap, human eval UI.

---

## 2026-06-22 to 2026-06-28 — Session 8: Phase 5 React frontend

**Built:**
- Full Vite + React 18 + TypeScript + Tailwind CSS frontend scaffold (`frontend/`)
- `frontend/src/api.ts` — typed API client: `createSession`, `sendMessage`, `submitAnswer`, `nextQuestion`, `streamHint`, `submitHumanScore`
- `Question.tsx` — displays stimulus, stem, 5 radio-button answer choices. Explicit `id`/`htmlFor` pairing (implicit label wrapping caused selection to break in Tailwind).
- `AnswerSelector.tsx` — submit button, disabled until an answer is selected
- `HintPanel.tsx` — "Get a hint" button that streams hint text token-by-token via `EventSource`. Three levels: indirect → direct → reveal. Resets on question change via `useEffect([questionId])`.
- `WeaknessHeatmap.tsx` — 15-type grid, green→red by weakness score, updates after every submission
- `HumanEvalPanel.tsx` — five 1–5 sliders (one per rubric dimension) + submit; posts to `POST /human-score` which appends to `eval/human_scores.jsonl`
- `Markdown.tsx` — lightweight inline markdown renderer (bold, bullets, hr) without a library, to handle agent message formatting
- `App.tsx` — full session flow: start → question → submit → feedback → hint → next question
- `GET /session/{id}/hint-stream` — SSE endpoint using `client.messages.stream()`; streams hint tokens with `data: {text}\n\n` and terminates with `data: [DONE]\n\n`
- `POST /human-score` — appends `HumanScoreRequest` to `eval/human_scores.jsonl`

**Architectural decisions:**
- Answer correctness check is deterministic (`POST /submit-answer`, no LLM). LLM only called on wrong answers for Socratic feedback. This eliminates latency and non-determinism from the answer-check path.
- All session responses include the current `question` and `weakness_scores` via `_build_response()`, so the frontend never has to parse question text out of agent messages.
- Wrong-answer Socratic feedback initially routed through the agent (`sendMessage`). This caused the agent to occasionally call `get_next_question` mid-feedback, advancing to a new question unexpectedly. Fixed by removing `sendMessage` from the wrong-answer path entirely and auto-triggering hint 1 via `HintPanel` (`autoTrigger={attempts === 1}`) — the hint endpoint has no tools and cannot advance the question.
- Session messages reset to `[]` on `/next-question` to prevent cross-question context bleed.

**Issues fixed:**
- Agent message duplicated question text — fixed by hiding agent message while a fresh question is waiting for first attempt.
- Radio buttons unselectable — implicit label wrapping conflicted with Tailwind; switched to explicit `htmlFor`/`id` pairing.
- Answer selection locked after wrong answer — `submitted` stayed `true`; fixed to `setSubmitted(false)` after wrong-answer path.
- HintPanel auto-triggered on correct answers — `attempts` increments regardless of correctness; fixed by adding `&& !questionResolved` guard on HintPanel render.
- Same question repeated on "Next question" — agent's `run_turn` returned unchanged `current_question`; fixed with a dedicated `/next-question` endpoint that calls `generate()` directly.
- Double-recording of attempts — both `/submit-answer` and the agent's `submit_answer` tool could record. Fixed with `_recorded_ids: set[str]` on TutorSession.

---

## 2026-07-08 — Session 9: Naïve baseline comparison (Phase 4 evaluation)

**Built:**
- `scripts/generate_naive_batch.py` — generates 30 LSAT questions using only the prompt "Write one LSAT logical reasoning question." No RAG, no schema enforcement, no type specification. A second Claude call parses the prose output into the `Question` schema (best-effort). Questions that fail parsing are counted as failures.
- `scripts/compare_baselines.py` — loads `eval/generated_samples.jsonl` (RAG scores) and `eval/naive_scores.jsonl`, computes mean ± std per dimension, runs two-sample Welch t-tests, prints a table, saves `eval/baseline_comparison.png`.
- Added `scipy` and `matplotlib` to dependencies.

**Results (n=30 each):**

| Dimension | RAG | Naïve | Δ | p |
|---|---|---|---|---|
| logical_validity | 4.53±0.50 | 3.60±0.61 | +0.93 | <0.001 |
| answer_uniqueness | 4.73±0.44 | 3.67±0.91 | +1.07 | <0.001 |
| distractor_quality | 3.93±0.44 | 3.03±0.41 | +0.90 | <0.001 |
| type_accuracy | 5.00±0.00 | 4.30±0.90 | +0.70 | <0.001 |
| stimulus_independence | 5.00±0.00 | 4.97±0.18 | +0.03 | 0.33 (n.s.) |
| **AVERAGE** | **4.64±0.22** | **3.91±0.48** | **+0.73** | **<0.001** |

All dimensions significant at p<0.01 except `stimulus_independence` (both conditions near ceiling). The naïve generator also clustered heavily on 4–5 question types (weaken, flaw, assumption_necessary) with no type diversity — a failure mode the RAG system avoids by design.

---

## 2026-07-14 — Session 10: Gated generator in production + parallel candidates + question cache

**Built:**
- `src/api.py` + `src/agent.py` — replaced `generate()` with `generate_gated()` on all question-serving paths. Every question a student sees is now the best of 5 scored candidates.
- `src/generator_gated.py` — parallelised candidate generation using `ThreadPoolExecutor(max_workers=5)`. All 5 generate+score pairs run concurrently. Wall-clock time reduced from ~30s (sequential) to ~8s (one API round-trip pair). Used `as_completed()` so results accumulate as they finish; individual failures are caught per-future.
- `src/question_cache.py` — `QuestionCache` singleton that pre-generates and caches `(Question, RubricScore)` pairs per question type. Target pool size: 3 per type (45 questions in memory). Background daemon thread continuously refills depleted types. `/next-question` pops from the cache instantly; cache miss falls back to synchronous `generate_gated` (~8s). Concurrency limited by `threading.Semaphore(3)` to avoid hammering the Anthropic API.
- `src/api.py` — lifespan context manager starts the cache on server startup and kicks off `pre_warm()` in a thread pool (non-blocking). Added `GET /cache-status` endpoint showing pool depth per type.
- `src/db.py` — added `threading.Lock` with double-checked locking around Chroma `PersistentClient` initialisation. Previously, 5 concurrent threads all hitting `get_client()` simultaneously caused `RustBindingsAPI` corruption. Lock ensures only one thread initialises the client; all others wait and reuse it.
- Frontend loading state: "Generating question…" shown while `currentQuestion` is null and `loading` is true.

**Effective student latency:** ~0ms (cache hit) vs ~8s (cache miss / cold start).

**Issues fixed:**
- Chroma `PersistentClient` not thread-safe on first initialisation — fixed with double-checked locking in `db.py`.
- `pre_warm()` blocking the asyncio event loop for ~40s, causing server to appear hung — fixed by removing `await` so it runs in a thread pool without blocking startup.

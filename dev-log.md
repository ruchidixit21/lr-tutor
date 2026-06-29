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

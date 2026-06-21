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

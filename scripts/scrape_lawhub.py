"""Scrape LSAT questions from LawHub (lawhub.lsac.org) using Playwright.

Playwright controls a real browser externally — it does not trigger LawHub's
JS-based DevTools detection. Uses the text API (not vision) to parse questions:
navigate to each question, read the visible text, send to claude-sonnet-4-6 to
extract the Question schema. Cheaper and more accurate than screenshot-based extraction.

Workflow:
  1. Authenticate (run once, saves a browser auth state file):
       uv run scripts/scrape_lawhub.py --login

  2. Rush through the section in LawHub (answer every question — answers don't matter).
     Complete the section. LawHub will enter review mode showing correct answers.

  3. Scrape in review mode (correct answers are visible):
       uv run scripts/scrape_lawhub.py --url "<review URL from browser>" \\
           --source-detail "PrepTest 140 Section 1" --count 25

  4. Load into Chroma:
       uv run scripts/load_vectors.py
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from dotenv import load_dotenv
from playwright.async_api import Page, async_playwright

from src.models import Question, QuestionSource

load_dotenv()

AUTH_FILE = Path(".lawhub_auth.json")

# ---------------------------------------------------------------------------
# Claude parsing prompt
# ---------------------------------------------------------------------------

PARSE_SYSTEM = """You extract a single LSAT Logical Reasoning question from the raw text content
of a LawHub web page. The text will include navigation noise (e.g. "Pause Section",
"Complete Section", "Prev", "Next", page numbers like "1 2 3 … 25", "Library", section
headings). Ignore all navigation text.

Output ONLY a JSON object — no commentary, no markdown fences — matching this schema:

{
  "question_type": "<one of the 15 values below>",
  "stimulus": "<the argument or passage, verbatim — left-hand panel>",
  "stem": "<the question asked, verbatim — starts with a number like '1.' or '2.'>",
  "choices": [
    {"label": "A", "text": "<verbatim>"},
    {"label": "B", "text": "<verbatim>"},
    {"label": "C", "text": "<verbatim>"},
    {"label": "D", "text": "<verbatim>"},
    {"label": "E", "text": "<verbatim>"}
  ],
  "correct_answer": "<A/B/C/D/E if marked correct (review mode shows a checkmark or green highlight), else empty string>"
}

Question type values — pick from the stem wording:
  assumption_necessary   → "requires the assumption", "assumes which of the following"
  assumption_sufficient  → "if assumed, allows the conclusion to be properly drawn", "completes the passage" (fill-in type)
  strengthen             → "most strengthens", "provides the most support for"
  weaken                 → "most weakens", "most seriously undermines"
  flaw                   → "flaw in the reasoning", "the reasoning is flawed because"
  inference              → "can be properly inferred", "most strongly supported by the statements"
  must_be_true           → "must be true", "must also be true"
  cannot_be_true         → "cannot be true", "impossible"
  paradox                → "helps to explain", "resolve the apparent discrepancy", "resolve the paradox"
  parallel_reasoning     → "most similar in its reasoning", "most parallel in structure"
  parallel_flaw          → "most similar flaw", "contains a flaw most similar to"
  point_of_disagreement  → "disagree about", "point of disagreement", "committed to disagreeing"
  evaluate               → "most useful to know", "most helpful in evaluating"
  principle_identify     → "best illustrates which principle", "principle most illustrated by"
  principle_apply        → "most in accord with the principle", "most consistent with the principle"

In review mode, the correct answer may appear with a checkmark (✓), the word "Correct",
or green styling rendered as extra text near a choice label. Identify it and return just
the letter (A/B/C/D/E).

If you cannot determine the correct answer, return empty string."""


async def _wait_for_question(page: Page) -> None:
    """Wait until the question content has loaded."""
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    # Extra pause so JS-rendered content settles
    await page.wait_for_timeout(800)


async def _get_page_text(page: Page) -> str:
    """Return visible text from the main content area, falling back to body."""
    for selector in ["main", "article", "#root", "#app", ".question-content", "body"]:
        try:
            el = page.locator(selector).first
            if await el.count() > 0:
                text = await el.inner_text(timeout=3000)
                if len(text.strip()) > 100:
                    return text
        except Exception:
            continue
    return await page.inner_text("body")


def _parse_with_claude(text: str, source_detail: str, client: anthropic.Anthropic) -> Question | None:
    """Send page text to claude-sonnet-4-6 text API and parse into a Question object."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=PARSE_SYSTEM,
        messages=[{"role": "user", "content": f"Page text:\n\n{text}"}],
    )
    raw = response.content[0].text.strip()
    try:
        data = json.loads(raw)
        data["source"] = QuestionSource.REAL_LSAT.value
        data["source_detail"] = source_detail
        return Question.model_validate(data)
    except Exception as e:
        print(f"    [warn] Claude parse failed — {e}\n    raw: {raw[:200]}", file=sys.stderr)
        return None


async def _scrape(url: str, output: str, source_detail: str, count: int | None) -> None:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    storage = str(AUTH_FILE) if AUTH_FILE.exists() else None
    if not storage:
        print(
            "No auth state found. Run with --login first to authenticate.",
            file=sys.stderr,
        )
        sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=storage,
            # Realistic viewport and user agent reduce bot-detection risk
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print(f"Navigating to {url} …")
        await page.goto(url, wait_until="domcontentloaded")
        await _wait_for_question(page)

        questions: list[Question] = []
        q_num = 0

        while True:
            q_num += 1
            text = await _get_page_text(page)
            detail = f"{source_detail} Q{q_num}"
            print(f"  Q{q_num}: extracting …", end="", flush=True)
            q = _parse_with_claude(text, detail, client)
            if q:
                questions.append(q)
                has_answer = "✓" if q.correct_answer else "?"
                print(f" {q.question_type.value} [answer={has_answer}]")
            else:
                print(" FAILED")

            if count and q_num >= count:
                break

            # Try to advance to next question — try several selectors in order
            clicked = False
            candidates = [
                page.get_by_role("button", name="Next", exact=False),
                page.get_by_role("link", name="Next", exact=False),
                page.locator("button:has-text('Next')"),
                page.locator("a:has-text('Next')"),
                page.locator("[aria-label*='Next' i]"),
            ]
            for candidate in candidates:
                try:
                    if await candidate.count() > 0:
                        is_enabled = await candidate.first.is_enabled(timeout=2000)
                        if is_enabled:
                            await candidate.first.click()
                            await _wait_for_question(page)
                            clicked = True
                            break
                except Exception:
                    continue

            if not clicked:
                # Log all buttons on page to help diagnose selector mismatches
                all_btns = await page.locator("button, a[role='button']").all_inner_texts()
                visible = [t.strip() for t in all_btns if t.strip()]
                print(f"\n  [debug] No Next button found after Q{q_num}. "
                      f"Buttons visible: {visible[:10]}")
                break

        await browser.close()

    if not questions:
        print("No questions extracted. Check the URL and auth state.")
        return

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a") as f:
        for q in questions:
            f.write(q.model_dump_json() + "\n")

    answered = sum(1 for q in questions if q.correct_answer)
    print(f"\nDone. {len(questions)} questions written to {output} ({answered} with correct answers).")
    if answered < len(questions):
        print(
            "Tip: re-run on the review URL after completing the section to pick up correct answers."
        )


async def _login(start_url: str) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(start_url)
        print("\nBrowser opened. Log in to LawHub, then come back here and press Enter.")
        input("Press Enter after logging in: ")
        await context.storage_state(path=str(AUTH_FILE))
        await browser.close()
    print(f"Auth state saved to {AUTH_FILE}")
    print("Add .lawhub_auth.json to .gitignore if not already there.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--login", action="store_true", help="Open browser to log in and save auth state")
    parser.add_argument("--url", help="URL of the LawHub section/review page to scrape")
    parser.add_argument("--output", default="data/corpus.jsonl", help="Output JSONL file (appended)")
    parser.add_argument("--source-detail", default="LSAC PrepTest", help='e.g. "PrepTest 140 Section 1"')
    parser.add_argument("--count", type=int, default=None, help="Number of questions to scrape (default: auto-detect via Next button)")
    args = parser.parse_args()

    if args.login:
        asyncio.run(_login(args.url or "https://lawhub.lsac.org"))
    elif args.url:
        asyncio.run(_scrape(args.url, args.output, args.source_detail, args.count))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

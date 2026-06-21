"""Convert a PDF file to per-page JPEG images ready for extract_from_scan.py.

Uses pymupdf (no external binary dependencies). Output images are named
page_001.jpg, page_002.jpg, etc. DPI defaults to 200 which is sufficient
for Claude's vision API to read printed LSAT text reliably.
"""
import argparse
import sys
from pathlib import Path

import fitz  # pymupdf


def convert(pdf_path: str, output_dir: str, dpi: int, pages: str | None) -> None:
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"Error: {pdf_path} not found", file=sys.stderr)
        sys.exit(1)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf))
    total = doc.page_count

    # parse optional page range "3-18" or "3,5,7"
    if pages:
        if "-" in pages:
            lo, hi = pages.split("-", 1)
            indices = list(range(int(lo) - 1, int(hi)))
        else:
            indices = [int(p) - 1 for p in pages.split(",")]
    else:
        indices = list(range(total))

    mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 is PDF's base DPI

    written = 0
    for i in indices:
        if i < 0 or i >= total:
            print(f"  [skip] page {i + 1} out of range (doc has {total} pages)", file=sys.stderr)
            continue
        page = doc[i]
        pix = page.get_pixmap(matrix=mat)
        out_path = out / f"page_{i + 1:03d}.jpg"
        pix.save(str(out_path))
        print(f"  page {i + 1:>{len(str(total))}} → {out_path.name}")
        written += 1

    doc.close()
    print(f"\nDone. {written} image(s) written to {output_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("output_dir", help="Directory to write JPEG images into")
    parser.add_argument(
        "--dpi", type=int, default=200, help="Render resolution (default: 200)"
    )
    parser.add_argument(
        "--pages",
        default=None,
        help='Pages to convert, e.g. "3-18" or "1,3,5". Default: all pages.',
    )
    args = parser.parse_args()
    convert(args.pdf, args.output_dir, args.dpi, args.pages)

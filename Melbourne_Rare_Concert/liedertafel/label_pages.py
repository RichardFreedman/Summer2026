"""Stamp a large boxed letter (A, B, C...) on each page of a PDF so pages can
be referred to easily. Optionally shows the page's number in a source PDF
underneath, matched by OCR text."""

import argparse
import difflib
import string
from pathlib import Path

import pymupdf


def source_page_numbers(doc: pymupdf.Document, source: pymupdf.Document) -> list[int | None]:
    """Match each page to a page of the source document by its text layer."""
    source_text = [p.get_text().strip() for p in source]
    result = []
    for page in doc:
        text = page.get_text().strip()
        scores = [difflib.SequenceMatcher(None, text, t).ratio() if t else 0.0 for t in source_text]
        best = max(range(len(scores)), key=scores.__getitem__)
        result.append(best + 1 if scores[best] > 0.6 else None)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--source", type=Path, help="original PDF, to print the source page number")
    ap.add_argument("--size", type=float, default=40, help="letter box size in points")
    ap.add_argument("--margin", type=float, default=14, help="distance from the top-right corner")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    origins = source_page_numbers(doc, pymupdf.open(args.source)) if args.source else [None] * len(doc)
    letters = string.ascii_uppercase
    for page, origin in zip(doc, origins):
        letter = letters[page.number]
        s, m = args.size, args.margin
        box = pymupdf.Rect(page.rect.x1 - m - s, m, page.rect.x1 - m, m + s)
        shape = page.new_shape()
        shape.draw_rect(box)
        shape.finish(color=(0, 0, 0), fill=(1, 1, 1), width=2)
        shape.commit()
        fs = s * 0.72
        width = pymupdf.get_text_length(letter, fontname="hebo", fontsize=fs)
        # Helvetica capitals are ~0.72 em tall; centre that on the box.
        baseline = pymupdf.Point(box.x0 + (s - width) / 2, box.y0 + (s + fs * 0.72) / 2)
        page.insert_text(baseline, letter, fontsize=fs, fontname="hebo")
        if origin:
            sub = pymupdf.Rect(box.x0 - 30, box.y1 + 2, box.x1 + 30, box.y1 + 14)
            page.insert_textbox(sub, f"orig. p.{origin}", fontsize=7, fontname="helv", align=pymupdf.TEXT_ALIGN_CENTER)
        print(f"page {page.number + 1}: {letter}" + (f" (source page {origin})" if origin else ""))
    doc.save(args.output, garbage=3, deflate=True)
    print("wrote", args.output)


if __name__ == "__main__":
    main()

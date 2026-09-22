"""Preprocess scanned PDFs for black-and-white printing.

Every image on each page (base scan plus any overlaid patches) is flattened:
the paper background is pushed to white and the ink towards black. The new
greyscale pixels are written back into the existing image objects, so page
geometry, stencil/soft masks and the OCR text layer are all preserved.
"""

import argparse
import zlib
from pathlib import Path

import cv2
import numpy as np
import pymupdf


def estimate_background(grey: np.ndarray, radius: int) -> np.ndarray:
    """Estimate the paper tone under the ink. A morphological closing
    (dilate then erode) removes dark strokes narrower than the kernel,
    leaving only paper; a blur then smooths the estimate."""
    h, w = grey.shape
    if min(h, w) < 3 * radius:
        # Too small for a local estimate (ornament patches): use a flat value.
        return np.full_like(grey, np.percentile(grey, 90))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius, radius))
    closed = cv2.morphologyEx(grey, cv2.MORPH_CLOSE, k)
    return cv2.GaussianBlur(closed, (0, 0), radius)


def flatten(grey: np.ndarray, radius: int) -> np.ndarray:
    """Divide out the background so paper becomes ~255 everywhere."""
    bg = estimate_background(grey, radius).astype(np.float32)
    norm = grey.astype(np.float32) / np.maximum(bg, 1.0)
    return np.clip(norm * 255.0, 0, 255).astype(np.uint8)


def stretch(grey: np.ndarray, black: float, white: float, gamma: float) -> np.ndarray:
    """Levels: values <= black -> 0, >= white -> 255, with a gamma curve."""
    x = (grey.astype(np.float32) - black) / max(white - black, 1.0)
    x = np.clip(x, 0.0, 1.0) ** gamma
    return (x * 255.0).astype(np.uint8)


def whiten_border(out: np.ndarray, grey: np.ndarray, shrink: int = 0) -> np.ndarray:
    """Replace the dark scanner-bed surround with white to save toner.
    The paper is the largest bright connected region of the original scan;
    everything outside its convex hull becomes white."""
    _, paper = cv2.threshold(grey, 90, 255, cv2.THRESH_BINARY)
    paper = cv2.morphologyEx(paper, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(paper)
    if n < 2:
        return out
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    contours, _ = cv2.findContours((labels == biggest).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull = cv2.convexHull(max(contours, key=cv2.contourArea))
    mask = np.zeros_like(out)
    cv2.fillConvexPoly(mask, hull, 255)
    if shrink > 0:
        # Pull the outline inwards to drop the gutter shadow along the edges.
        mask = cv2.erode(mask, np.ones((2 * shrink + 1, 2 * shrink + 1), np.uint8))
    result = out.copy()
    result[mask == 0] = 255
    return result


def process(rgb: np.ndarray, args, is_base: bool) -> np.ndarray:
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    out = grey if args.mode == "levels" else flatten(grey, args.radius)
    if args.upscale > 1:
        # Upsample smoothly before the curve so the ragged 200 dpi letter
        # edges are rounded rather than hardened; printers resolve far more
        # than 200 dpi, so this reads as less grain on paper.
        f = args.upscale
        out = cv2.resize(out, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
        grey = cv2.resize(grey, None, fx=f, fy=f, interpolation=cv2.INTER_LINEAR)
        if args.smooth > 0:
            out = cv2.GaussianBlur(out, (0, 0), args.smooth)
    out = stretch(out, args.black, args.white, args.gamma)
    if args.mode == "bilevel":
        _, out = cv2.threshold(out, args.threshold, 255, cv2.THRESH_BINARY)
    if args.mask_border and is_base:
        out = whiten_border(out, grey, args.border_shrink * args.upscale)
    return out


def rewrite_image(doc: pymupdf.Document, xref: int, grey: np.ndarray, jpeg_quality: int) -> None:
    """Overwrite an image object's pixels with 8-bit grey, keeping its
    dictionary (and therefore any /Mask or /SMask reference) intact."""
    if jpeg_quality:
        ok, buf = cv2.imencode(".jpg", grey, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        doc.update_stream(xref, buf.tobytes(), compress=False)
        doc.xref_set_key(xref, "Filter", "/DCTDecode")
    else:
        doc.update_stream(xref, zlib.compress(grey.tobytes(), 9), compress=False)
        doc.xref_set_key(xref, "Filter", "/FlateDecode")
    doc.xref_set_key(xref, "Width", str(grey.shape[1]))
    doc.xref_set_key(xref, "Height", str(grey.shape[0]))
    doc.xref_set_key(xref, "ColorSpace", "/DeviceGray")
    doc.xref_set_key(xref, "BitsPerComponent", "8")
    doc.xref_set_key(xref, "DecodeParms", "null")
    doc.xref_set_key(xref, "Decode", "null")


def page_images(doc: pymupdf.Document, page: pymupdf.Page):
    """Yield (xref, is_base) for every real image on the page, skipping the
    mask images that are only referenced from another image."""
    infos = page.get_images(full=True)
    mask_xrefs = {im[1] for im in infos if im[1]}
    for im in infos:
        xref = im[0]
        if xref in mask_xrefs:
            continue
        rects = page.get_image_rects(xref)
        is_base = any(abs(r.get_area() - page.rect.get_area()) / page.rect.get_area() < 0.05 for r in rects)
        yield xref, is_base


def parse_pages(spec: str) -> set[int]:
    pages: set[int] = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        pages.update(range(int(a), int(b or a) + 1))
    return pages


def parse_overrides(specs: list[str]) -> dict[int, dict]:
    """"13:black=60,gamma=1.0" -> {13: {"black": 60.0, "gamma": 1.0}}"""
    result: dict[int, dict] = {}
    for spec in specs:
        pages, _, settings = spec.partition(":")
        kv = {}
        for item in settings.split(","):
            k, _, v = item.partition("=")
            k = k.replace("-", "_")
            kv[k] = v if k == "mode" else float(v)
        for p in parse_pages(pages):
            result.setdefault(p, {}).update(kv)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--mode", choices=["levels", "flatten", "bilevel"], default="flatten")
    ap.add_argument("--radius", type=int, default=41, help="background estimation kernel (px)")
    ap.add_argument("--upscale", type=int, default=2, help="integer upsampling factor before the curve (1 = off)")
    ap.add_argument("--smooth", type=float, default=1.2, help="gaussian sigma after upsampling (px)")
    ap.add_argument("--black", type=float, default=100, help="input level mapped to black")
    ap.add_argument("--white", type=float, default=235, help="input level mapped to white")
    ap.add_argument("--gamma", type=float, default=1.3, help=">1 darkens mid-greys")
    ap.add_argument("--threshold", type=int, default=128, help="bilevel cut-off")
    ap.add_argument("--mask-border", action="store_true", help="whiten the scanner surround")
    ap.add_argument("--border-shrink", type=int, default=8, help="px to trim inside the paper outline")
    ap.add_argument("--pages", type=parse_pages, help="keep only these pages, e.g. 1,3,7-9")
    ap.add_argument("--override", action="append", default=[], metavar="PAGES:k=v,...",
                    help="per-page settings, e.g. 13:black=60,gamma=1.0 (repeatable)")
    ap.add_argument("--jpeg-quality", type=int, default=0, help="0 = lossless Flate; else JPEG quality")
    ap.add_argument("--png-dir", type=Path, help="also dump each processed image here")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    if args.pages:
        doc.select([p - 1 for p in sorted(args.pages) if p <= len(doc)])
    overrides = parse_overrides(args.override)
    if args.png_dir:
        args.png_dir.mkdir(parents=True, exist_ok=True)
    for page in doc:
        original_number = sorted(args.pages)[page.number] if args.pages else page.number + 1
        page_args = argparse.Namespace(**vars(args))
        for k, v in overrides.get(original_number, {}).items():
            setattr(page_args, k, int(v) if k in ("radius", "threshold", "border_shrink", "upscale") else v)
        images = list(page_images(doc, page))
        base = [x for x, is_base in images if is_base]
        if not base:
            print(f"page {page.number + 1}: no full-page scan found, skipped")
            continue
        base_xref = base[0]
        bw, bh = doc.extract_image(base_xref)["width"], doc.extract_image(base_xref)["height"]
        # Render the composited page (base scan + patches) at the base scan's
        # own resolution, so the seams between layers vanish before processing.
        mat = pymupdf.Matrix(bw / page.rect.width, bh / page.rect.height)
        pix = page.get_pixmap(matrix=mat, colorspace=pymupdf.csRGB, alpha=False)
        rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
        out = process(rgb, page_args, True)
        if args.png_dir:
            cv2.imwrite(str(args.png_dir / f"p{page.number + 1:02d}.png"), out)
        sx, sy = out.shape[1] / page.rect.width, out.shape[0] / page.rect.height
        for xref, is_base in images:
            if is_base:
                crop = out
            else:
                # Patch keeps its own dimensions and mask; fill it with the
                # matching region of the processed composite.
                r = page.get_image_rects(xref)[0]
                x0, y0 = int(round((r.x0 - page.rect.x0) * sx)), int(round((r.y0 - page.rect.y0) * sy))
                x1, y1 = int(round((r.x1 - page.rect.x0) * sx)), int(round((r.y1 - page.rect.y0) * sy))
                info = doc.extract_image(xref)
                region = out[max(y0, 0):y1, max(x0, 0):x1]
                crop = cv2.resize(region, (info["width"] * page_args.upscale, info["height"] * page_args.upscale), interpolation=cv2.INTER_AREA)
            rewrite_image(doc, xref, crop, args.jpeg_quality)
        note = f" (override {overrides[original_number]})" if original_number in overrides else ""
        print(f"page {original_number}: {pix.width}x{pix.height} composite, {len(images)} image objects -> {page_args.mode}{note}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output, garbage=4, deflate=True)
    print("wrote", args.output)


if __name__ == "__main__":
    main()

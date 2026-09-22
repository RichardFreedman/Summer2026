"""Add text-image links to the TEI edition.

For every page, text-bearing elements (verse lines, headings, list items,
paragraphs, bylines, notes, folios) are fuzzy-matched against the line boxes
of the OCR layer in the original PDF. Each match becomes a <zone> on the
page's <surface>, in the pixel space of the facsimile image, and the element
receives a facs pointer to it. Figures are located by image analysis: large
dark connected components that overlap no text line.

Usage: link_zones.py [in.xml] [out.xml]
"""

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
NS = {"t": TEI}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
here = Path(__file__).parent
LINKABLE = {"l", "head", "p", "item", "label", "byline", "note", "trailer", "fw", "titlePart", "docDate"}
MIN_SCORE = 0.55
MAX_SHORT_HEIGHT_PT = 45  # a line-like element matched over more than this is a false match

# Hand-placed zones (PDF points) for what neither OCR nor blob detection can find:
# ("figure", index-on-page) or (element name, start of normalised text) -> list of boxes.
OVERRIDES = {
    1: [(("figure", 0), [(53, 55, 321, 150)]), (("figure", 1), [(53, 462, 321, 492)]),
        (("titlePart", "melbourne liedertafel"), [(83, 205, 312, 335)])],
    4: [(("figure", 0), [(152, 78, 224, 93)]), (("head", "the orchestra"), [(133, 55, 241, 78)]),
        # blackletter section labels: absent from the OCR layer entirely
        (("label", "violins"), [(66, 104, 102, 114)]), (("label", "violas"), [(66, 257, 94, 266)]),
        (("label", "'cellos"), [(65, 318, 95, 327)]), (("label", "basses"), [(66, 363, 97, 372)]),
        (("label", "flutes"), [(66, 407, 97, 416)]), (("label", "piccolo"), [(188, 104, 227, 114)]),
        (("label", "oboes"), [(188, 131, 219, 140)]), (("label", "clarionets"), [(188, 159, 241, 168)]),
        (("label", "bassoons"), [(188, 191, 233, 200)]), (("label", "horns"), [(188, 219, 219, 228)]),
        (("label", "trumpets"), [(188, 269, 233, 278)]), (("label", "trombones"), [(188, 296, 244, 306)]),
        (("label", "tuba"), [(188, 338, 210, 347)]), (("label", "tympani"), [(188, 360, 224, 369)]),
        (("label", "cymbals"), [(188, 381, 305, 390)]), (("label", "librarian"), [(188, 407, 233, 416)])],
    6: [(("head", "the liedertafel will be assisted"), [(72, 70, 310, 130)])],
    7: [(("figure", 0), [(30, 46, 332, 186), (30, 186, 111, 492)]), (("figure", 1), [(150, 268, 282, 297)])],
    18: [(("figure", 0), [(180, 292, 220, 312)]), (("figure", 1), [(178, 404, 226, 421)])],
}


def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^a-z0-9äöüœ' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ocr_lines(page: pymupdf.Page):
    """OCR lines as (x0, y0, x1, y1, text) in PDF points, in OCR order."""
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            words = []
            for span in line["spans"]:
                # split span text into words with approximate boxes by character width
                sx0, sy0, sx1, sy1 = span["bbox"]
                t = span["text"]
                if not t.strip():
                    continue
                cw = (sx1 - sx0) / max(len(t), 1)
                pos = 0
                for m in re.finditer(r"\S+", t):
                    words.append((sx0 + m.start() * cw, sy0, sx0 + m.end() * cw, sy1, m.group()))
            lines.append([x0, y0, x1, y1, text, words])
    return lines


def page_of_nodes(text_el):
    """Map every node under <text> to the index of the last <pb> before it."""
    pages, current = {}, -1
    for node in text_el.iter():
        if isinstance(node, etree._Comment):
            continue
        if node.tag == f"{{{TEI}}}pb":
            current += 1
        pages[node] = current
        # tail text belongs to the same page as the node's end
    return pages


def element_text_on_page(el, k, pages):
    """Concatenate the text of el that falls on page k (by node assignment)."""
    parts = []
    def walk(n):
        if isinstance(n, etree._Comment):
            return
        if n.tag == f"{{{TEI}}}pb":
            return
        if n.tag == f"{{{TEI}}}expan":
            return
        if n.text and pages.get(n, -1) == k:
            parts.append(n.text)
        for c in n:
            walk(c)
            if c.tail and pages.get(c, -1) == k:
                # tail follows child c; a pb child moves later text to the next page
                parts.append(c.tail)
    walk(el)
    return norm(" ".join(parts))


def is_leaf_linkable(el):
    tag = etree.QName(el).localname
    if tag not in LINKABLE:
        return False
    parent = etree.QName(el.getparent()).localname if el.getparent() is not None else ""
    if tag == "label" and parent == "head":
        return False
    if tag in ("item", "note") and el.find(f"t:list", NS) is not None:
        return False
    if tag == "note" and el.find("t:p", NS) is not None:
        return False
    if tag == "item" and (el.find("t:list", NS) is not None):
        return False
    return True


def best_match(target, lines, used, max_span=8):
    """Best match for target: a run of consecutive fully-unused OCR lines, or a
    run of unused words inside one line (for short targets on multi-column pages).
    `used` holds (line index, word index) pairs. Returns (score, descriptor)."""
    best = (0.0, None)
    n = len(lines)
    def line_free(li):
        return all((li, w) not in used for w in range(len(lines[li][5])))
    for i in range(n):
        if not line_free(i):
            continue
        acc = ""
        for span in range(max_span):
            j = i + span
            if j >= n or not line_free(j):
                break
            acc = (acc + " " + norm(lines[j][4])).strip()
            if not acc or len(acc) > 2.5 * len(target) + 20:
                if len(acc) > 2.5 * len(target) + 20:
                    break
                continue
            sm = SequenceMatcher(None, target, acc)
            if sm.quick_ratio() < best[0]:
                continue
            score = sm.ratio()
            if score > best[0]:
                best = (score, ("lines", i, j))
    tw = len(target.split())
    if tw <= 8:
        for li, line in enumerate(lines):
            words = line[5]
            for a in range(len(words)):
                if (li, a) in used:
                    continue
                acc = ""
                for b in range(a, min(len(words), a + tw + 2)):
                    if (li, b) in used:
                        break
                    acc = (acc + " " + norm(words[b][4])).strip()
                    if not acc:
                        continue
                    sm = SequenceMatcher(None, target, acc)
                    if sm.quick_ratio() < best[0]:
                        continue
                    score = sm.ratio()
                    if score > best[0] + 1e-9:
                        best = (score, ("words", li, a, b))
    return best


def match_box(lines, desc):
    """Bounding box (points) and the (line, word) pairs consumed by a match."""
    if desc[0] == "lines":
        _, i, j = desc
        seg = lines[i:j + 1]
        pairs = {(li, w) for li in range(i, j + 1) for w in range(len(lines[li][5]))}
        return (min(l[0] for l in seg), min(l[1] for l in seg), max(l[2] for l in seg), max(l[3] for l in seg)), pairs, ("line" if i == j else "block")
    _, li, a, b = desc
    ws = lines[li][5][a:b + 1]
    return (min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws)), {(li, w) for w in range(a, b + 1)}, "line"


def figure_boxes(img_path, text_boxes_px, min_area):
    """Large dark connected components not overlapping text boxes."""
    g = cv2.imread(str(img_path), 0)
    _, bw = cv2.threshold(g, 160, 255, cv2.THRESH_BINARY_INV)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw)
    boxes = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_area or w > 0.9 * g.shape[1] or h < 8 or w < 8:
            continue  # too small, the page border, or a printed rule
        box = [x, y, x + w, y + h]
        if any(not (box[2] < t[0] or box[0] > t[2] or box[3] < t[1] or box[1] > t[3]) for t in text_boxes_px):
            continue
        boxes.append(box)
    # merge boxes that share a horizontal band or nearly touch (parts of one ornament)
    merged = True
    while merged and len(boxes) > 1:
        merged = False
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                A, B = boxes[a], boxes[b]
                y_overlap = min(A[3], B[3]) - max(A[1], B[1]) > 0.5 * min(A[3] - A[1], B[3] - B[1])
                near = not (A[2] + 12 < B[0] or B[2] + 12 < A[0] or A[3] + 12 < B[1] or B[3] + 12 < A[1])
                if y_overlap or near:
                    boxes[a] = [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3])]
                    del boxes[b]
                    merged = True
                    break
            if merged:
                break
    return [tuple(b) for b in boxes]


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "UDC20260028-21.xml"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(src), parser)
    root = tree.getroot()
    pdf = pymupdf.open(str(here.parent / "UDC20260028-21.pdf"))
    text_el = root.find("t:text", NS)
    pages = page_of_nodes(text_el)
    pbs = text_el.findall(".//t:pb", NS)
    surfaces = {s.get(XML_ID): s for s in root.findall(".//t:surface", NS)}

    # clear previous run
    for z in root.findall(".//t:zone", NS):
        z.getparent().remove(z)
    for el in text_el.iter():
        if isinstance(el, etree._Comment) or etree.QName(el).localname == "pb":
            continue
        if el.get("facs") is not None:
            del el.attrib["facs"]

    report = []
    for k, pb in enumerate(pbs):
        surface = surfaces[pb.get("facs").lstrip("#")]
        page = pdf[k]
        img = cv2.imread(str(here / surface.find("t:graphic", NS).get("url")), 0)
        H, W = img.shape
        sx, sy = W / page.rect.width, H / page.rect.height
        surface.set("ulx", "0"); surface.set("uly", "0"); surface.set("lrx", str(W)); surface.set("lry", str(H))
        lines = ocr_lines(page)
        used = set()
        zone_n = 0
        text_boxes_px = []

        def add_zone(box_px, el, kind):
            nonlocal zone_n
            zone_n += 1
            zid = f"z{k + 1:02d}-{zone_n:03d}"
            z = etree.SubElement(surface, f"{{{TEI}}}zone")
            z.set(XML_ID, zid)
            for name, val in zip(("ulx", "uly", "lrx", "lry"), box_px):
                z.set(name, str(int(round(val))))
            z.set("type", kind)
            z.tail = "\n    "
            prev = el.get("facs")
            el.set("facs", f"{prev} #{zid}" if prev else f"#{zid}")
            return zid

        overridden = set()
        figs_all = [f for f in text_el.iter(f"{{{TEI}}}figure") if pages.get(f) == k]
        for (kind, key), boxes in OVERRIDES.get(k + 1, []):
            if kind == "figure":
                target_el = figs_all[key] if key < len(figs_all) else None
            else:
                target_el = next((e for e in text_el.iter(f"{{{TEI}}}{kind}") if pages.get(e) == k
                                  and element_text_on_page(e, k, pages).startswith(key)), None)
            if target_el is None:
                report.append(f"  page {k + 1}: override target {kind} {key!r} not found")
                continue
            overridden.add(target_el)
            for b in boxes:
                box = (b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy)
                text_boxes_px.append(box)
                add_zone(box, target_el, "figure" if kind == "figure" else "manual")
        elements = [el for el in text_el.iter() if not isinstance(el, etree._Comment) and is_leaf_linkable(el) and el not in overridden]
        elements = [el for el in elements if len(element_text_on_page(el, k, pages)) >= 2]
        matched = unmatched = 0
        results = [None] * len(elements)  # (x0,y0,x1,y1) in points
        pad = 2
        targets = [element_text_on_page(el, k, pages) for el in elements]
        for idx in sorted(range(len(elements)), key=lambda i: -len(targets[i])):
            el, target = elements[idx], targets[idx]
            score, desc = best_match(target, lines, used)
            need = MIN_SCORE if len(target) >= 12 else 0.6
            if desc is None or score < need:
                continue
            box, pairs, kind = match_box(lines, desc)
            tag = etree.QName(el).localname
            limit = None if tag in ("p", "note") else (MAX_SHORT_HEIGHT_PT if tag == "head" else 30)
            if limit is not None and (box[3] - box[1]) > limit:
                continue
            used.update(pairs)
            results[idx] = (*box, kind)
        # fallback: place unmatched elements in the vertical gap between matched neighbours,
        # using any unused OCR line found in that gap, else the gap itself
        for idx, el in enumerate(elements):
            if results[idx] is not None:
                continue
            prev_box = next((results[p] for p in range(idx - 1, -1, -1) if results[p]), None)
            next_box = next((results[p] for p in range(idx + 1, len(elements)) if results[p]), None)
            top = prev_box[3] if prev_box else 0
            bottom = next_box[1] if next_box else page.rect.height
            if bottom - top < 4:
                unmatched += 1
                report.append(f"  page {k + 1}: no match for <{etree.QName(el).localname}> {element_text_on_page(el, k, pages)[:50]!r} (gap {bottom - top:.0f}pt)")
                continue
            tag = etree.QName(el).localname
            limit = 22 if tag == "fw" else 50
            if bottom - top > limit and (bottom - top > 120 or tag == "fw"):
                # a wide gap: a heading sits just above what follows, a folio just below what precedes
                if next_box is not None and tag != "fw":
                    top = bottom - limit
                else:
                    bottom = top + limit
            cands = [n for n, l in enumerate(lines) if all((n, w) not in used for w in range(len(l[5]))) and l[1] >= top - 2 and l[3] <= bottom + 2 and (l[2] - l[0]) > 25]
            if cands:
                target = element_text_on_page(el, k, pages)
                n = max(cands, key=lambda n: SequenceMatcher(None, target, norm(lines[n][4])).ratio())
                used.update((n, w) for w in range(len(lines[n][5])))
                l = lines[n]
                results[idx] = (l[0], l[1], l[2], l[3], "line")
            else:
                xs = [b for b in (prev_box, next_box) if b]
                x0 = min(b[0] for b in xs); x1 = max(b[2] for b in xs)
                results[idx] = (x0, top + 3, x1, bottom - 3, "estimated")
            report.append(f"  page {k + 1}: placed <{etree.QName(el).localname}> {element_text_on_page(el, k, pages)[:40]!r} by position ({results[idx][4]})")
        for el, r in zip(elements, results):
            if r is None:
                continue
            box = ((r[0] - pad) * sx, (r[1] - pad) * sy, (r[2] + pad) * sx, (r[3] + pad) * sy)
            text_boxes_px.append(box)
            add_zone(box, el, r[4])
            matched += 1

        # figures on this page, in document order, matched to image blobs top-to-bottom
        figs = [f for f in figs_all if f not in overridden]
        if figs:
            blobs = figure_boxes(here / surface.find("t:graphic", NS).get("url"), text_boxes_px, min_area=250)
            blobs = sorted(sorted(blobs, key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))[:len(figs)], key=lambda b: (b[1], b[0]))
            for f, b in zip(figs, blobs):
                add_zone(b, f, "figure")
            if len(blobs) != len(figs):
                report.append(f"  page {k + 1}: {len(figs)} figure(s) in TEI, {len(blobs)} blob(s) found")
        # tidy whitespace inside surface
        if len(surface):
            surface.text = "\n    "
            surface[-1].tail = "\n  "
        print(f"page {k + 1:2d}: {matched} matched, {unmatched} unmatched, {len(figs)} figure(s)")
    print("\n".join(report))
    for sib in root.itersiblings(preceding=True):
        sib.tail = "\n"
    tree.write(str(out), encoding="utf-8", xml_declaration=True, pretty_print=False)
    print("wrote", out)


if __name__ == "__main__":
    main()

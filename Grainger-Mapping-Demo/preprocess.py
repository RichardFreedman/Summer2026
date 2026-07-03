"""
Cleans the raw OCR'd TXT in preparation for parsing into structured data.

Will have to customized per catalogue book. A lot of this will hopefully be unnecessary in the future, since 
the OCR instructions will be better (the OCR this first time around left in a lot of artifacts that should've been 
left out) but some kind of TXT cleaning will still be necessary regardless
"""

# used in Python 3.13 so that classes don't instantly throw NameErrors if they aren't defined yet; this is generally just necessary for a lot of things
from __future__ import annotations

import re
from dataclasses import dataclass, field

"""
DE-COLUMNIZATION
"""

# Regex for finding page heads, e.g. "AUSTIN        8        BACH"
RE_PAGE_HEAD = re.compile(r"^[A-Z' .&()À-Ü-]{2,}\s{3,}\d{1,3}\s{3,}[A-Z' .&()À-Ü-]{2,}\s*$")
RE_PAGE_NUM = re.compile(r"^\s*\d{1,3}\s*$")

# A couple of globally true variables for finding where the OCR decided to place the column gap.
GAP_START_MIN = 8     # a column gap never starts this early
GAP_END_MIN = 33      # start of right column falls in [GAP_END_MIN,
GAP_END_MAX = 72      # GAP_END_MAX] on two-column pages
RIGHT_ONLY_COL = 30   # lines blank up to here are right-column-only
LONG_LINE = 62        # lines longer than this must show a gap on 2-col pages
COVERAGE = 0.7        # fraction of long left-bearing lines that must gap
MIN_LONG_LINES = 5


def _interior_gaps(line: str) -> list[tuple[int, int]]:
    """Regex finds interior gaps of >=2 spaces whose END (start of the right column)
    is in the 'middle' of the line (aka might indicate two columns)"""
    return [m.span() for m in re.finditer(r" {2,}", line.rstrip())
            if m.start() >= GAP_START_MIN and GAP_END_MIN <= m.end() <= GAP_END_MAX]


def decolumnize(text: str) -> str:
    """Decolumnizes text that was interleaved into two columns.

    Works page by page (page heads / bare page numbers are boundaries).
    Pages the OCR already emitted column-by-column are left untouched.
    """
    raw_lines = [l.rstrip("\r") for l in text.split("\n")]

    blocks: list[list[str]] = [[]]
    for line in raw_lines:
        if RE_PAGE_HEAD.match(line) or RE_PAGE_NUM.match(line):
            blocks.append([])
            continue
        blocks[-1].append(line)

    out: list[str] = []
    for block in blocks:
        out.extend(_decolumnize_block(block))
        out.append("")  # soft break at page boundaries
    return "\n".join(out)


def _decolumnize_block(block: list[str]) -> list[str]:
    nonblank = [l for l in block if l.strip()]
    if len(nonblank) < 6:
        return block

    # A page is interleaved two-column iff its LONG lines consistently 
    # show an interior multi-space gap in the middle. (Pages the OCR
    # already emitted column-by-column have no long lines at all.)
    long_lines = [l for l in nonblank if len(l.rstrip()) > LONG_LINE
                  and l[:RIGHT_ONLY_COL].strip()]   # ignore right-only lines
    gapped = [l for l in long_lines if _interior_gaps(l)]
    if len(long_lines) < MIN_LONG_LINES or len(gapped) / len(long_lines) < COVERAGE:
        return block

    # Consensus gap/"river" = median start-of-right-column over gapped lines.
    ends = sorted(g[1] for l in gapped for g in [_interior_gaps(l)[0]])
    river = ends[len(ends) // 2]

    left: list[str] = []
    right: list[str] = []
    for line in block:
        if not line.strip():
            left.append("")
            right.append("")
            continue
        l, r = _split_line(line, river)
        left.append(l)
        right.append(r)
    while left and not left[-1]:
        left.pop()
    while right and not right[-1]:
        right.pop()
    return left + [""] + right


def _split_line(line: str, river: int) -> tuple[str, str]:
    line = line.rstrip()
    # Right-column-only line (deep leading indent).
    if line[:RIGHT_ONLY_COL].strip() == "":
        return "", line.strip()
    gaps = _interior_gaps(line)
    if gaps:
        # Split at the gap whose end is nearest the consensus river.
        s, e = min(gaps, key=lambda g: abs(g[1] - river))
        return line[:s].rstrip(), line[e:].rstrip()
    if len(line) <= river + 2:
        return line, ""          # left column only
    # Long line, no clean gap (OCR merged the columns): fall back to the
    # single space nearest the river.
    spaces = [m.start() for m in re.finditer(r" ", line)]
    if spaces:
        s = min(spaces, key=lambda p: abs(p - river))
        return line[:s].rstrip(), line[s + 1:].rstrip()
    return line, ""


"""
Segmentation
"""

RE_ENTRY_NUM = re.compile(r"^(MG [A-Z]\d/[A-Z0-9':.-]+)\s*$")
RE_HAS_CHILD_SUFFIX = re.compile(r":\d+\s*$")


def normalize_ocr(text: str) -> str:
    """Fix systematic OCR hallucinations in classification numbers
    (e.g. 'MG CI/HIL-28' -> 'MG C1/HIL-28')."""
    return re.sub(r"\bMG ([A-Z])[Il](?=[/:])", r"MG \g<1>1", text)


def _is_heading(line: str) -> bool:
    """Composer authority heading: ALL-CAPS surname(s), optional forenames
    and dates, e.g. 'BACH, Johann Sebastian 1685-1750'"""
    s = line.strip()
    if not s or s.startswith(("MG ", "+")):
        return False
    first = s.split(",")[0].strip()
    if len(first) < 3 or not re.fullmatch(r"[A-Z][A-Z' .&()-]+", first):
        return False
    if re.fullmatch(r"[IVX]+\.?", first):
        return False
    return True


@dataclass
class Unit:
    """One segmentation unit: a heading or a whole entry (includig its children)"""
    kind: str                    # "heading" or "entry" or "front_matter"
    number: str | None           # MG number for entries
    heading: str | None          # governing composer heading (entries only)
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip("\n")


def segment(text: str) -> list[Unit]:
    """Split de-columnized text into heading / entry units.

    Rules:
    - new entry = line that is exactly an `MG ...` classification number,
      UNLESS the number ends `:n` (a child part's own number -> belongs to
      the entry above);
    - `+` lines belong to the entry above;
    - ALL-CAPS `SURNAME, Forename dddd-dddd` lines are composer headings.
    """
    units: list[Unit] = []
    current: Unit | None = None
    current_heading: str | None = None

    for line in text.split("\n"):
        m = RE_ENTRY_NUM.match(line.strip())
        if m and not RE_HAS_CHILD_SUFFIX.search(m.group(1)):
            current = Unit("entry", m.group(1), current_heading, [line.strip()])
            units.append(current)
            continue
        if m:  # `:n` child number -> keep with current entry
            if current is not None:
                current.lines.append(line.strip())
            continue
        if _is_heading(line) and not line.startswith(" "):
            # Cut right-column bleed on pages the de-columnizer missed.
            heading_text = re.split(r" {6,}", line.strip())[0].strip()
            current_heading = heading_text
            units.append(Unit("heading", None, None, [heading_text]))
            current = None
            continue
        if current is not None:
            current.lines.append(line)
        elif line.strip():
            if units and units[-1].kind in ("heading", "front_matter"):
                units[-1].lines.append(line)
            else:
                units.append(Unit("front_matter", None, None, [line]))

    # Collapse runs of blank lines inside units
    for u in units:
        cleaned: list[str] = []
        for l in u.lines:
            if l.strip() or (cleaned and cleaned[-1].strip()):
                cleaned.append(l.rstrip())
        u.lines = cleaned
    return units


"""
Batching
"""

@dataclass
class Batch:
    entries: list[Unit]

    @property
    def numbers(self) -> list[str]:
        return [e.number or "?" for e in self.entries]

    @property
    def text(self) -> str:
        """Format the batch text w/ empty lines delimiting between entries"""
        parts: list[str] = []
        last_heading = None
        for e in self.entries:
            if e.heading and e.heading != last_heading:
                parts.append(e.heading)
                last_heading = e.heading
            parts.append(e.text)
        return "\n\n".join(parts)


def make_batches(units: list[Unit], batch_size: int = 5) -> list[Batch]:
    """Batches "entry" units. An entry unit already contains its `+` children, so parent+children are always in the same batch."""
    entries = [u for u in units if u.kind == "entry"]
    return [Batch(entries[i:i + batch_size]) for i in range(0, len(entries), batch_size)]


def clean_entries(units: list[Unit]) -> list[Unit]:
    """Ignore fake entries that appear real by having headers (e.g. OCR artifacts and stray references) and dedupe entries by classification number"""
    best: dict[str, Unit] = {}
    order: list[str] = []
    for u in units:
        if u.kind != "entry":
            continue
        body = u.text[len(u.number):].strip() if u.text.startswith(u.number) else u.text
        # Real entries are ISBD prose; appendix/index artifacts are lists of
        # numbers with (almost) no lowercase text.
        if len(body) < 20 or sum(c.islower() for c in body) < 15:
            continue
        if u.number not in best:
            order.append(u.number)
            best[u.number] = u
        elif len(u.text) > len(best[u.number].text):
            best[u.number] = u
    return [best[n] for n in order]


# look for where the appendix starts so everything after it is disqualified
RE_APPENDIX = re.compile(r"^\s*APPENDIX\s+\d+\s*$", re.MULTILINE)


def catalogue_body(text: str) -> str:
    """Cut off the appendices/index: they repeat classification numbers in
    and would generate thousands of fake entries"""
    m = RE_APPENDIX.search(text)
    return text[:m.start()] if m else text


def preprocess(text: str) -> list[Unit]:
    units = segment(decolumnize(normalize_ocr(catalogue_body(text))))
    entries = clean_entries(units)
    return entries

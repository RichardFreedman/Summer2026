# PDF OCR Extraction — Usage

Two scripts extract machine-readable text from scanned/PDF documents using
PaddleOCR. Both convert each PDF page to a PNG image, OCR the images in
parallel, and write the recognized text back out as JSON and TXT.

## Prerequisites

- Python 3 with the packages in `requirements.txt` installed:
  ```bash
  pip install -r requirements.txt
  ```
  (run inside whatever environment/venv you use for this project).
- macOS: no extra steps needed — both scripts set
  `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` internally to avoid a fork-safety
  crash under `multiprocessing`.

## Files

| File | Purpose |
|---|---|
| `multipage_extraction.py` | Extracts text from a **single** PDF. Prompts interactively for the PDF path. |
| `multipdf_extraction.py` | Batch-processes **every PDF** in `input/`, writing results to `output/` plus a `manifest.csv`. |
| `ocr_worker.py` | Standalone OCR worker (per-line text + confidence score, no page numbers) used by `Multi_Extraction.ipynb`. Not used by either script above. |

Both scripts run OCR at `DPI = 200` (set as a constant near the top of the
`__main__` block) — a compromise between accuracy and speed. Lower it for
faster/rougher extraction, raise it (toward 300) if small text is getting
misread; each step up roughly doubles the pixel count and processing time
per page.

## Running `multipage_extraction.py`

```bash
python3 multipage_extraction.py
```

It's interactive:
1. Prompts for the path to the PDF file.
2. Proposes a temp directory (next to the PDF) for the intermediate page
   images and asks you to confirm or override it.
3. Converts each page to a PNG, OCRs them across up to 4 processes, then
   deletes the temp image folder.

**Output**, written alongside the source PDF:
- `<pdf_basename>.json` — structured page data (see below)
- `<pdf_basename>.txt` — plain-text version with `===Page N===` headers

## Running `multipdf_extraction.py`

```bash
python3 multipdf_extraction.py
```

No prompts — it reads every `.pdf` file from an `input/` folder and writes
results to an `output/` folder. **Both are relative to whatever directory
you run the command from**, so `cd` into the project folder first (the one
containing `input/` and `output/`) before running it.

For each PDF in `input/` it writes, into `output/`:
- `<pdf_basename>.json`
- `<pdf_basename>.txt`
- one row in `output/manifest.csv` recording the mapping and status

If a given PDF fails (corrupt file, etc.), it's logged as an error row in
the manifest and the batch continues with the next file rather than
aborting.

### manifest.csv columns

| Column | Meaning |
|---|---|
| `pdf_filename` | Source file, from `input/` |
| `txt_filename` | Corresponding `.txt` output in `output/` |
| `json_filename` | Corresponding `.json` output in `output/` |
| `num_pages` | Page count (blank if the PDF errored before this was known) |
| `status` | `success`, or `error: <message>` |

## Output formats

**JSON** — a list of per-page objects, sorted by page number:

```json
[
  {
    "pagenum": 0,
    "text": ["Chapter 1", "This is the first line...", "..."]
  },
  {
    "pagenum": 1,
    "text": ["This is page two...", "..."]
  }
]
```

`text` is a flat list of the individual text fragments PaddleOCR detected
per page (one per detected text box), in PaddleOCR's own detection order —
not necessarily true reading order on multi-column or oddly laid-out pages.

**TXT** — the same content flattened to plain text, one section per page,
fragments joined with spaces (not newlines, since PaddleOCR's fragments
are per detected box rather than per real line):

```
===Page 0===
Chapter 1 This is the first line of extracted text. Some other fragment.

===Page 1===
This is page two, continuing the document. Another fragment.
```

This TXT format is intended as the input for downstream LLM-based
structured-data extraction.

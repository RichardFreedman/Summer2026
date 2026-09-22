# Liedertafel 1899: print preparation and TEI edition

Source for the rare-music session's work on two archival scans from the
University of Melbourne collection: UDC20260028-21, the twenty-page programme
for the Melbourne Liedertafel's 263rd concert (23 October 1899), and
UDC20260028-69, a 1902 circular and concert card. The scans themselves are in
`../sources/`.

Two outputs came from it:

- **Print-ready files and a re-set transcription** of a five-page selection,
  for the in-room part of the session. `docs/METHOD.md` records exactly how
  this was done and why.
- **A page-by-page TEI edition** of the 1899 programme with facsimile images
  and text-image linking, published as a single self-contained web page at
  <https://dhworkshops.researchsoftware.unimelb.edu.au/liedertafel/>. The built
  page lives in `site/` and is what `deploy/liedertafel/` serves.

## Layout

```
prep_print.py          flatten scans to clean black-and-white for printing (PyMuPDF, OpenCV)
label_pages.py         stamp boxed letters on pages so they can be referred to in the room
transcription/         re-set HTML transcription of the selection and render.py (Playwright) to print it
fonts/                 Old Standard and UnifrakturMaguntia, used by the transcription
docs/METHOD.md         the write-up of the print-preparation work, with figures in docs/img/
tei/
  UDC20260028-21.xml   the TEI edition
  facs/                facsimile JPEGs, one per page (plus the untouched originals)
  link_zones.py        adds <zone> text-image links by matching text against the OCR layer
  validate.py          validates the TEI against tei_all.rng in schema/
  viewer_template.html the viewer shell
  build_viewer.py      embeds TEI and images into the template -> tei/viewer.html
site/
  index.html           the built viewer (a copy of tei/viewer.html)
  UDC20260028-21.xml   the TEI file, offered for download
```

Scratch renders (`work/`) and the large print PDFs (`output/`) are not committed.

## Rebuilding the edition

Python 3.14 with [uv](https://docs.astral.sh/uv/); dependencies are in
`pyproject.toml` and `uv.lock`.

```bash
uv sync
uv run tei/validate.py                  # should print nothing
uv run tei/link_zones.py                # only if the text or zones changed
uv run tei/build_viewer.py              # writes tei/viewer.html
cp tei/viewer.html site/index.html
cp tei/UDC20260028-21.xml site/UDC20260028-21.xml
```

Commit `site/` and run `deploy/liedertafel/deploy.sh` from the repository root
to publish.

## Print preparation

```bash
uv run prep_print.py ../sources/UDC20260028-21.pdf -o output/UDC20260028-21_print.pdf
uv run label_pages.py output/UDC20260028-21_print.pdf -o output/labelled.pdf
uv run transcription/render.py transcription/UDC20260028-21_subset.html output/transcription.pdf
```

See `docs/METHOD.md` for the reasoning behind each step and the options.

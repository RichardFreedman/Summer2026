# Melbourne Rare Concert Programs

Tools for turning OCR'd Melbourne rare-book concert/performance programs into structured, analyzable data, using an LLM (with a Pydantic schema) to extract facts, flag uncertain readings for human review, and then explore patterns across the resulting corpus (venues, dates, presenters, composers, works, and performers).

The workflow is three notebooks, meant to be run in order:

1. **`RareBooks_DataExtraction.ipynb`** — extract structured data from each program PDF.
2. **`RareBooks_ReviewFlags.ipynb`** — turn the extraction's uncertainty flags into a ranked CSV for human review.
3. **`RareBooks_PatternAnalysis.ipynb`** — chart trends and answer research questions across the extracted corpus.

## 1. `RareBooks_DataExtraction.ipynb`

**Scope/purpose:** For each concert program, extracts the venue, date, presenting institution/organization, patrons/sponsors, composers and works performed, and performers (with instrument or vocal part). Each extracted item is tagged with its source page number and a verbatim excerpt, and carries `review_flags` for anything the LLM had to infer or guess at — so every fact can be traced back to where it was found and how confident the model was. The extraction step is resumable: it only calls the LLM for files not already in its cache, runs several files concurrently, and saves progress after every file.

- **Inputs:** OCR'd text (`extracted_texts/`) and `sources/manifest.csv` for per-program metadata.
- **Outputs (in `Structured Data/`):**
  - `concert_program_by_file.json` — extraction results grouped by source file (the working cache, updated after every file).
  - `concert_program_items.json` / `concert_program_items.csv` — a flat list, one row per extracted item (venue, date, organization, patron, work, or performer), with its `record_type`, source filename, manifest metadata, and page number.

## 2. `RareBooks_ReviewFlags.ipynb`

**Scope/purpose:** Converts the `review_flags` attached to items during extraction into a single ranked review queue, so a human can efficiently check the items most likely to need correction. Each flag is classified by severity — **High** (possible OCR misreading/illegibility), **Medium** (the LLM inferred or standardized a field), or **Low** (an intentional, documented schema choice) — and an item with multiple flags takes its highest severity.

- **Input:** `Structured Data/concert_program_items.json`.
- **Output:** `Structured Data/review_queue.csv`, sorted worst-first (High → Medium → Low, then by document/page) so a reviewer can work down the list and stop once they've covered what matters most.

## 3. `RareBooks_PatternAnalysis.ipynb`

**Scope/purpose:** Explores patterns across the extracted corpus — conductors, composers, and performers across ensembles, and how they change over time — using Plotly Express charts. Includes worked examples (e.g. conductors of the Musashino Academia Musicae, most-performed composers, pianists by ensemble, Melbourne Liedertafel violinists over time) meant as templates for new questions.

- **Inputs:** `Structured Data/concert_programs_events.json` (one row per concert, with role/person and composer/work credits) as the primary source; `Structured Data/concert_program_items.json` for questions needing named performers that aren't captured at the event level.
- **Output:** in-notebook charts and tables (not persisted to disk).

## Requirements and tools

Install with `pip install -r requirements.txt`.

| Tool / package | Used in | Purpose |
|---|---|---|
| `langchain`, `langchain-community`, `langchain-core` | Data Extraction | LLM orchestration, PDF loading (`PyPDFLoader`), prompt templates |
| `langchain-openai` | Data Extraction | OpenAI provider integration for `init_chat_model` |
| `pypdf` | Data Extraction | PDF parsing backend used by `PyPDFLoader` |
| `pydantic` | Data Extraction | Schema classes the LLM's structured output is validated against |
| An OpenAI API key (`OPENAI_API_KEY`) | Data Extraction | Notebook is set to call `gpt-5` via `init_chat_model`; prompts for the key on first run if not already set. Swap `model_provider`/`model_name` to use a different LLM |
| `pandas` | Review Flags, Pattern Analysis | Building/sorting the review queue; reshaping credit data into long/tidy tables |
| `plotly.express` | Review Flags, Pattern Analysis | Charts (severity breakdown, conductors/composers/pianists/violinists over time) |
| `asyncio` (standard library) | Data Extraction | Runs extraction calls concurrently across files |
| `ipykernel` | All three | Runs the notebooks in Jupyter |

## Folder guide

- `sources/` — source PDFs and `manifest.csv`.
- `extracted_texts/` — OCR output feeding the extraction notebook.
- `Structured Data/` — all JSON/CSV inputs and outputs shared across the three notebooks.
- `code/Langchain_for_Rare_Books_draft_only.ipynb` — an earlier, separate extraction pass over a different (non-concert-program) source; its flag log (`langchain_flags.csv`) isn't used by the current review-queue or pattern-analysis notebooks since it doesn't carry the same fields, but is available for reference.
- `slide_tiles/` — figures used in presentations about this workflow.

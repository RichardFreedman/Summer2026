# Ask the transcripts

A Streamlit app that answers questions from ELAN transcripts in the PARADISEC
archive by retrieval-augmented generation: the question is matched against
passages of the transcripts, and a language model answers only from the
passages it is given, citing each one. Built for the workshop from the
companion notebook `Paradesic_Text_LLM_Chroma.ipynb`.

Deployed at <https://dhworkshops.researchsoftware.unimelb.edu.au/paradisec-transcripts/>
(shared workshop login). Deployment lives in `deploy/paradisec-transcripts/`.

## What it does

- **Ask a question**: retrieves the most similar passages (3 to 8) and produces
  a short cited answer with `gpt-4o-mini`. The sources are shown beneath with
  links to the item and the transcript file in the catalogue.
- **Find passages**: the same retrieval without the language model, optionally
  limited to chosen items.
- **What is in the corpus**: every indexed transcript with its item, region,
  languages and catalogue link.
- **How this is computed**: a dialog with the recipe and the live source of the
  functions involved.

## The corpus and its conditions

The corpus is currently the **NT1 South Efate (Vanuatu)** collection deposited
by Nick Thieberger: 58 transcripts (one of the 59 downloaded files is empty) from 28 Open items. Closed items are
excluded at load time (`access_condition_name` must start with `Open`), and
the MMT1 material from the notebook is not included.

Transcripts are access-conditioned material. They are **never committed to
this repository or baked into the image**. The app reads manifest CSVs from
`DATA_DIR` (mounted from `deploy/paradisec-transcripts/data/` on the server,
which is gitignored) and builds its vector store into `STORE_DIR` on first run.
Before any passage is displayed, the user must tick that they have read and
agree to PARADISEC's [Conditions of Access](https://www.paradisec.org.au/deposit/access-conditions/);
the sidebar carries the depositor credit, DOI and citation. Metadata is
CC BY-NC-SA 4.0.

## Files

- `app.py`: the Streamlit interface, the agreement gate, and the code dialog.
- `rag.py`: corpus loading and filtering, line-aware chunking (2,000 characters,
  300 overlap), OpenAI embeddings (`text-embedding-3-large`), a persistent
  Chroma store with change detection, retrieval and answering. No Streamlit.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `/data` | folder holding `*_metadata.csv` manifests with a `text` column |
| `STORE_DIR` | `/store` | where the Chroma store is persisted |
| `OPENAI_API_KEY` | required | for embeddings and answers |
| `RAG_EMBEDDING_MODEL` | `text-embedding-3-large` | |
| `RAG_CHAT_MODEL` | `gpt-4o-mini` | |
| `RAG_FAKE_EMBEDDINGS` | unset | set to `1` to run offline with hash-based vectors and no model calls (tests only) |

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATA_DIR=./data STORE_DIR=./store OPENAI_API_KEY=sk-...
mkdir -p data && cp /path/to/nt1_metadata.csv data/
streamlit run app.py
```

The manifest CSV is the one written by the notebook's "Writing the Manifest
CSV" step: one row per essence with `full_identifier`, `title`, `region`,
`dialect`, `languages`, `access_condition_name`, `essence_filename`,
`essence_permalink`, `download_status` and `text`.

## Costs

Building the index embeds about 790 passages once (a few cents). Each question
is one embedding call and one `gpt-4o-mini` completion, well under a cent.

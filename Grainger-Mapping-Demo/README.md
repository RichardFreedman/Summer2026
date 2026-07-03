# Grainger → EMu demo 

This is a Streamlit demo of the TXT → structured-metadata pipeline, using the prompt
bundle (`bundle/`) and an OCR'd TXT of the _Grainger's Collection of Music by Other Composers_ 
sample catalogue. The demo converts batches of TXT catalogue entries into intermediate JSONs
to be loaded into an EMu system after manual review. 

The streamlit is available at grainger-mapping-demo.streamlit.app.

## How to run

    pip install -r requirements.txt
    streamlit run Home_🏠.py

To query the LLM, you must enter an OpenAI API key in the sidebar.

## Process

1. **Preprocess cleaning (deterministic, `preprocess.py`)**
    - Decolumnizes the TXT, which accidentally left a bunch of entries formatted
    as double columns.
    - Changes `MG / CI` to `MG / C1`, the former of which is an OCR hallucination
    - Segments the TXT into entries
    - Groups a number of entries into batches based on GUI input (default is 5) 
2. **Parse** 
    - OpenAI model based on GUI input (default is gpt-4o-mini) via langchain, temperature 0. 
    System prompt = `system_prompt.md` + `field_mapping.json` + `output_schema.json` + `worked_examples.json`.
    - The system prompt attempts to have the LLM flag low confidence conversion instead of guessing.
3. **Validate**: 
    - every response checked against `output_schema.json` using the `Draft 2020-12` JSON validator; 
    if errors are returned, prompts the LLM to retry with the errors attached.
4. **Review**: 
    - entries flagged for review are displayed; valid records are returned as a downloadable JSON file

## Post-demo deployment

The idea is to host this on a Django site that can act as a dashboard for the full pipeline on any
uploaded PDF (OCR --> TXT --> JSON). This may require some cheap hosting.

Before that, a sample EMu export from the Grainger curators is needed so I can customize the JSON schemas to
what their backend actually looks like.


# RAG System Demo

The preprocessed TXT is also fed into a RAG system via Chroma DB. Because the cleaned TXT is already chunked
into entries during preprocessing, the Chroma DB setup (in `chroma-db_creation.py`) forgoes the usual text
splitting process and uses those entries instead as chunks.
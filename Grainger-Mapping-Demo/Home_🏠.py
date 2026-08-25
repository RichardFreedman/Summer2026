import streamlit as st


st.set_page_config(page_title='Home', page_icon='🏠')

st.title("Grainger Catalogue --> EMu Structured Metadata Pipeline Demo")

st.markdown(
    """
    This demo converts batches of OCR'd TXT catalogue entries into intermediate JSONs to be loaded into an EMu digital 
    collections management system after manual review. The OCR'd catalogue is cleaned into uniform entries, grouped 
    into batches of entries of adjustable size, parsed into EMu-like JSON, and validated against the desired JSON schema. 
    Low-confidence and erroneous conversions are flagged for review and excluded from the output JSON. To use the demo, 
    an openai API key must be entered into the sidebar. More information on the conversion process can be found in the 
    GitHub's README.

    A more complete deployment of this demo would be capable of running this process on any input PDF or TXT, and would
    also have to be customized per institution, since every EMu integration is heavily customized. A sample EMu export
    is necessary to tailor the JSON schemas per institution.

    A deterministic post-process cleaning is also needed to properly attribute the parties involved in each piece and to
    link parent and child entries together. This post-processing is not yet present in this demo.

    Also included is a RAG (retrieval-augmented generation) dashboard that leverages the cleaning done for the above
    conversion by using the uniform entries as text chunks. Those chunks are vectorized and stored in a vector database
    before app deployment. The RAG system is capable of taking a needle-in-a-haystack query and looking for the text
    chunks (aka catalogue entries) that are most likely to be relevant to that query, displaying those chunks, and 
    using it to build a response. You are welcome (and I would encourage you) to simply ignore the response and use the
    chunk search as a kind of semantic search engine.
"""
)
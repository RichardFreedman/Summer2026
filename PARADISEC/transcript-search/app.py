"""Ask the transcripts: retrieval-augmented search over PARADISEC ELAN transcripts.

Run with:  streamlit run app.py   (see README for DATA_DIR / STORE_DIR / OPENAI_API_KEY)
"""
from __future__ import annotations

import inspect
import os

import pandas as pd
import streamlit as st

import rag

st.set_page_config(page_title="Ask the transcripts", page_icon="🗣️", layout="wide")

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"


# --------------------------------------------------------------------------- #
# Data and store (cached per process)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def manifest() -> pd.DataFrame:
    return rag.load_manifest()


@st.cache_resource(show_spinner=False)
def store() -> rag.Store:
    return rag.open_store()


df = manifest()
summary = rag.corpus_summary(df)
st_store = store()

if df.empty:
    st.error(f"No corpus found. Put one or more `*_metadata.csv` manifests in `{rag.DATA_DIR}`.")
    st.stop()

if not rag.FAKE and not os.environ.get("OPENAI_API_KEY"):
    st.error("No OpenAI API key is configured. Set `OPENAI_API_KEY` in the environment before starting the app.")
    st.stop()

# Build or rebuild the vector store on first run or when the corpus changes.
if rag.needs_build(df, st_store):
    st.info("Preparing the search index for this corpus. This happens once, and takes a minute or two.")
    bar = st.progress(0.0, text="starting")
    rag.build_store(df, st_store, progress=lambda done, total, label: bar.progress(done / max(total, 1), text=label))
    st.rerun()

build_info = rag.build_info()
n_chunks = st_store.count

# --------------------------------------------------------------------------- #
# Sidebar: what this is, whose it is, and the agreement gate
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("Ask the transcripts")
    st.caption("Retrieval-augmented search over ELAN transcripts from the PARADISEC archive.")
    st.markdown(
        f"**Corpus:** {summary['items']} items · {summary['essences']} transcripts · "
        f"{n_chunks} passages · collection{'s' if len(summary['collections']) > 1 else ''} "
        f"{', '.join(summary['collections'])}")
    st.markdown(
        "**South Efate (Vanuatu)**, collection NT1, deposited by Nick Thieberger (University of Melbourne). "
        "Recordings made in and around Erakor village since 1995, in Nafsan (South Efate) and Bislama. "
        "Only items marked *Open* are included; closed items are not indexed.")
    st.markdown("[Collection in the catalogue](https://catalog.paradisec.org.au/collections/NT1) · "
                "DOI 10.4225/72/56E97595B6D0A")
    st.divider()
    st.markdown("#### Conditions of access")
    st.markdown(
        "Transcript passages are shown under PARADISEC's "
        f"[Conditions of Access]({rag.ACCESS_CONDITIONS_URL}): scholarly and educational use only, not for "
        "profit; acknowledge the depositor and PARADISEC; do not copy or redistribute the material. "
        "Metadata is CC BY-NC-SA 4.0.")
    agreed = st.checkbox("I have read and agree to the PARADISEC Conditions of Access", key="agreed")
    st.divider()
    st.caption("Citation: Thieberger, Nick (2012). *South Efate (Vanuatu)*. PARADISEC. "
               "https://doi.org/10.4225/72/56E97595B6D0A")


# --------------------------------------------------------------------------- #
# "How this is computed" dialog
# --------------------------------------------------------------------------- #
RECIPE = '''
import chromadb
from openai import OpenAI
client = OpenAI()

# 1. Each transcript is cut into ~2000-character passages that overlap by 300 characters,
#    with the item's title, identifier, region and languages prepended so they are searchable too.
passages = [header + chunk for chunk in chunk_text(transcript)]

# 2. Every passage is turned into a vector with an embedding model and stored in Chroma.
vectors = client.embeddings.create(model="text-embedding-3-large", input=passages).data
collection.add(documents=passages, embeddings=[v.embedding for v in vectors], metadatas=metadata, ids=ids)

# 3. A question is embedded the same way; the nearest passages by cosine similarity are retrieved.
q = client.embeddings.create(model="text-embedding-3-large", input=[question]).data[0].embedding
hits = collection.query(query_embeddings=[q], n_results=6)

# 4. The passages, numbered, are handed to a chat model with instructions to answer only from them
#    and to cite [Source n]. Nothing from outside the passages is meant to appear in the answer.
reply = client.chat.completions.create(model="gpt-4o-mini", messages=[...])
'''


@st.dialog("How this is computed", width="large")
def code_dialog():
    st.markdown("**The recipe**, from transcript files to an answer with citations:")
    st.code(RECIPE.strip(), language="python")
    st.markdown("**What the app actually runs** (from `rag.py`):")
    for f in (rag.chunk_text, rag.embed, rag.build_store, rag.retrieve, rag.answer):
        st.code(inspect.getsource(f), language="python")
    st.markdown(f"Embedding model `{rag.EMBEDDING_MODEL}`, chat model `{rag.CHAT_MODEL}`. "
                "The index is built once on the server and reused; each question costs two small API calls.")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.markdown("### Ask a question of the South Efate transcripts")
st.markdown(
    "Type a question in plain English. The app finds the transcript passages most similar to it and asks a "
    "language model to answer **only from those passages**, citing each one. Open the sources to read the "
    "passages themselves and follow the links back to the recordings in the catalogue.")
if st.button("How this is computed", icon=":material/code:", type="tertiary"):
    code_dialog()

tab_ask, tab_find, tab_corpus = st.tabs(["Ask a question", "Find passages", "What is in the corpus"])


def passage_card(i: int, p: dict, show_text: bool) -> None:
    head = f"**Source {i}** · *{p['title']}* · `{p['full_identifier']}` · similarity {p['score']:.2f}"
    with st.expander(head, expanded=(i <= 2)):
        bits = [b for b in (p.get("region"), p.get("dialect"), p.get("languages")) if b]
        st.caption(" · ".join(bits) + f" · file `{p['essence_filename']}`")
        st.markdown(f"[Item in the catalogue]({p['catalogue_url']}) · [Transcript file]({p['essence_permalink']})")
        if show_text:
            body = p["text"].split("\n\n", 1)[-1]          # drop the metadata header we prepended
            st.text(body if len(body) <= 1800 else body[:1800] + "\n…")
        else:
            st.info("Agree to the Conditions of Access in the sidebar to read the passage.")


EXAMPLES = ["What do people say about traditional ceremonies and songs?",
            "How is the pig referred to, and in what contexts?",
            "What stories are told about the origins of villages?",
            "Which speakers talk about church or Christianity?"]

with tab_ask:
    c1, c2 = st.columns([3, 1])
    question = c1.text_input("Your question", placeholder=EXAMPLES[0], key="question")
    k = c2.slider("Passages to use", 3, 8, 6)
    st.caption("Try: " + " · ".join(f"*{e}*" for e in EXAMPLES[1:]))
    if question.strip():
        if not agreed:
            st.warning("Please agree to the Conditions of Access in the sidebar first. The answer quotes from the transcripts.")
        else:
            with st.spinner("Finding passages and writing an answer…"):
                passages = rag.retrieve(st_store, question, k=k)
                reply = rag.answer(question, passages)
            st.markdown("#### Answer")
            st.markdown(reply)
            st.caption("The answer is generated from the passages below and may misread them. Check the sources.")
            st.markdown("#### Sources")
            for i, p in enumerate(passages, 1):
                passage_card(i, p, show_text=True)

with tab_find:
    st.markdown("Skip the language model: search for passages and read them directly.")
    c1, c2 = st.columns([3, 1])
    q2 = c1.text_input("Search for", placeholder="a phrase, a topic, a name…", key="find")
    k2 = c2.slider("Results", 3, 15, 8)
    items = df.drop_duplicates("full_identifier")
    picked = st.multiselect("Limit to items (optional)", items["full_identifier"].tolist(),
                            format_func=lambda i: f"{i} · {items.set_index('full_identifier').loc[i, 'title'][:60]}")
    if q2.strip():
        hits = rag.retrieve(st_store, q2, k=k2, item_filter=picked or None)
        for i, p in enumerate(hits, 1):
            passage_card(i, p, show_text=agreed)

with tab_corpus:
    st.markdown(
        "Every transcript indexed by the app. All are ELAN (`.eaf`) files whose items are marked Open; "
        "the seven closed items in NT1 are excluded, as are the recordings themselves.")
    table = (df.groupby(["full_identifier", "title", "region", "languages", "catalogue_url"], as_index=False)
             .agg(transcripts=("essence_filename", "count"), characters=("text", lambda s: int(s.str.len().sum())))
             .sort_values("full_identifier"))
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={"catalogue_url": st.column_config.LinkColumn("catalogue", display_text="open"),
                                "characters": st.column_config.NumberColumn(format="%d")})
    st.caption(f"{summary['essences']} transcripts, {summary['chars']:,} characters, {n_chunks} passages in the index"
               + (f" (embedding model {build_info['embedding_model']})" if build_info else "") + ".")

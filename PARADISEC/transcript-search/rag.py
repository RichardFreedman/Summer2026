"""Corpus loading, chunking, embedding and retrieval for the transcript search app.

No Streamlit in here. The corpus is one or more PARADISEC manifest CSVs (as
written by the companion notebook) in DATA_DIR; the vector store is a Chroma
collection persisted in STORE_DIR. Only essences whose download succeeded and
whose item is Open are indexed.

Settings come from the environment:
  DATA_DIR              where the *_metadata.csv manifests live      (default /data)
  STORE_DIR             where the Chroma store persists              (default /store)
  OPENAI_API_KEY        required for embedding and answering
  RAG_EMBEDDING_MODEL   default text-embedding-3-large
  RAG_CHAT_MODEL        default gpt-4o-mini
  RAG_FAKE_EMBEDDINGS   set to 1 for offline tests (deterministic hash vectors)
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import chromadb
import numpy as np
import pandas as pd

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STORE_DIR = Path(os.environ.get("STORE_DIR", "/store"))
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "text-embedding-3-large")
CHAT_MODEL = os.environ.get("RAG_CHAT_MODEL", "gpt-4o-mini")
FAKE = os.environ.get("RAG_FAKE_EMBEDDINGS") == "1"

COLLECTION = "paradisec_transcripts"
CHUNK_SIZE = 2000        # characters, matching the notebook
CHUNK_OVERLAP = 300
ACCESS_CONDITIONS_URL = "https://www.paradisec.org.au/deposit/access-conditions/"


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
def load_manifest(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Every indexable essence across all manifests: downloaded OK and Open."""
    frames = []
    for csv in sorted(data_dir.glob("*_metadata.csv")):
        df = pd.read_csv(csv)
        df["manifest"] = csv.name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    ok = (df["download_status"] == "ok") & df["text"].fillna("").str.strip().ne("")
    open_ = df["access_condition_name"].fillna("").str.startswith("Open")
    df = df[ok & open_].copy()
    df["source_id"] = df["full_identifier"] + "/" + df["essence_filename"]
    df["catalogue_url"] = ("https://catalog.paradisec.org.au/collections/"
                           + df["collection_id"] + "/items/" + df["full_identifier"].str.split("-", n=1).str[1])
    for col in ("region", "dialect", "languages", "title"):
        df[col] = df[col].fillna("")
    return df.reset_index(drop=True)


def corpus_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"items": 0, "essences": 0, "chars": 0, "collections": []}
    return {"items": int(df["full_identifier"].nunique()), "essences": len(df),
            "chars": int(df["text"].str.len().sum()),
            "collections": sorted(df["collection_id"].unique().tolist())}


def manifest_fingerprint(df: pd.DataFrame) -> str:
    h = hashlib.md5()
    for _, r in df.sort_values("source_id").iterrows():
        h.update(r["source_id"].encode()); h.update(hashlib.md5(r["text"].encode()).digest())
    h.update(EMBEDDING_MODEL.encode()); h.update(f"{CHUNK_SIZE}/{CHUNK_OVERLAP}".encode())
    return h.hexdigest()


def header_for(row: pd.Series) -> str:
    return (f"Title: {row['title']}\nIdentifier: {row['full_identifier']}\n"
            f"Region: {row['region']}\nLanguages: {row['languages']}\n\n")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on line boundaries into pieces of about `size` characters with overlap."""
    lines = [l for l in text.splitlines() if l.strip()]
    chunks, buf, buf_len = [], [], 0
    for line in lines:
        if buf and buf_len + len(line) + 1 > size:
            chunks.append("\n".join(buf))
            # carry the tail of the previous chunk forward as overlap
            tail, tail_len = [], 0
            for l in reversed(buf):
                if tail_len + len(l) + 1 > overlap:
                    break
                tail.insert(0, l); tail_len += len(l) + 1
            buf, buf_len = tail, tail_len
        buf.append(line); buf_len += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks or [text[:size]]


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def _openai():
    from openai import OpenAI
    return OpenAI()


def embed(texts: list[str]) -> list[list[float]]:
    if FAKE:
        out = []
        for t in texts:
            rng = np.random.default_rng(int(hashlib.md5(t.encode()).hexdigest()[:8], 16))
            v = rng.standard_normal(64); out.append((v / np.linalg.norm(v)).tolist())
        return out
    client = _openai()
    vectors = []
    for i in range(0, len(texts), 100):
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts[i:i + 100])
        vectors.extend(d.embedding for d in resp.data)
    return vectors


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #
@dataclass
class Store:
    client: "chromadb.api.ClientAPI"
    collection: "chromadb.Collection"

    @property
    def count(self) -> int:
        return self.collection.count()


def open_store(store_dir: Path = STORE_DIR) -> Store:
    store_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(store_dir))
    col = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    return Store(client, col)


def build_info(store_dir: Path = STORE_DIR) -> dict | None:
    """What the current store was built from, or None if it has never been built."""
    p = store_dir / "build.json"
    return json.loads(p.read_text()) if p.exists() else None


def store_fingerprint(store_dir: Path = STORE_DIR) -> str | None:
    info = build_info(store_dir)
    return info["fingerprint"] if info else None


def needs_build(df: pd.DataFrame, store: Store, store_dir: Path = STORE_DIR) -> bool:
    return store.count == 0 or store_fingerprint(store_dir) != manifest_fingerprint(df)


def build_store(df: pd.DataFrame, store: Store, store_dir: Path = STORE_DIR, progress=None) -> dict:
    """(Re)build the collection from the manifest. `progress(done, total, label)` is optional."""
    store.client.delete_collection(COLLECTION)
    store.collection = store.client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    ids, docs, metas = [], [], []
    for _, r in df.iterrows():
        header = header_for(r)
        for i, chunk in enumerate(chunk_text(r["text"])):
            ids.append(hashlib.md5(f"{r['source_id']}#{i}".encode()).hexdigest())
            docs.append(header + chunk)
            metas.append({"source_id": r["source_id"], "full_identifier": r["full_identifier"],
                          "collection_id": r["collection_id"], "title": r["title"], "region": r["region"],
                          "dialect": r["dialect"], "languages": r["languages"], "essence_filename": r["essence_filename"],
                          "essence_permalink": r["essence_permalink"], "catalogue_url": r["catalogue_url"], "chunk": i})
    total = len(docs)
    for i in range(0, total, 100):
        if progress:
            progress(i, total, f"embedding chunks {i + 1}–{min(i + 100, total)} of {total}")
        vecs = embed(docs[i:i + 100])
        store.collection.add(ids=ids[i:i + 100], documents=docs[i:i + 100], metadatas=metas[i:i + 100], embeddings=vecs)
    if progress:
        progress(total, total, "done")
    info = {"fingerprint": manifest_fingerprint(df), "chunks": total, "essences": len(df),
            "items": int(df["full_identifier"].nunique()), "embedding_model": EMBEDDING_MODEL}
    (store_dir / "build.json").write_text(json.dumps(info, indent=2))
    return info


# --------------------------------------------------------------------------- #
# Retrieval and answering
# --------------------------------------------------------------------------- #
def retrieve(store: Store, question: str, k: int = 6, item_filter: list[str] | None = None) -> list[dict]:
    where = {"full_identifier": {"$in": item_filter}} if item_filter else None
    res = store.collection.query(query_embeddings=embed([question]), n_results=k, where=where,
                                 include=["documents", "metadatas", "distances"])
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": doc, "score": 1 - dist, **meta})
    return out


SYSTEM_PROMPT = """You are an expert in language documentation and linguistic fieldwork, familiar with the
languages of Vanuatu and the PARADISEC archive. Answer the question using only the numbered source passages
provided. Each passage comes from an ELAN transcript, laid out as "TIER: text" lines; tiers may hold the
original-language transcription, a translation, or a speaker.

Cite passages as [Source n] after the statements they support, and quote short phrases where useful.
If the passages do not answer the question, say so plainly rather than guessing.
Write one or two short paragraphs."""


def answer(question: str, passages: list[dict]) -> str:
    if FAKE:
        return "(offline test mode: no language model call was made) " + " ".join(f"[Source {i}]" for i in range(1, len(passages) + 1))
    context = "\n\n".join(
        f"[Source {i}] '{p['title']}' ({p['full_identifier']}, {p['essence_filename']}):\n{p['text']}"
        for i, p in enumerate(passages, 1))
    client = _openai()
    resp = client.chat.completions.create(
        model=CHAT_MODEL, temperature=0,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": f"Passages:\n\n{context}\n\nQuestion: {question}"}])
    return resp.choices[0].message.content

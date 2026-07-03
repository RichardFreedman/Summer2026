"""
Creates a chroma db out of the parsed entries created by preprocess.py
"""

import os
from pathlib import Path
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma

from preprocess import preprocess

HERE = Path(__file__).parent
DATA = HERE / "data" / "Grainger_Catalog_Other_Composers.txt"


"""
ONLY RUN THIS FILE ONCE.
"""

os.environ["OPENAI_API_KEY"] = 'openai-api-key-here'

embeddings = OpenAIEmbeddings(model='text-embedding-3-large')

vector_store = Chroma(
    collection_name="Etude_samples", # I forgot to change this name on the initial run so it has to stay now
    embedding_function=embeddings,
    persist_directory='./chroma-db'
)

text = DATA.read_text(encoding="utf-8")
docs = [Document(page_content=e.text) for e in preprocess(text)]
ids = [f"id_{i}" for i in range(len(docs))]

vector_store.add_documents(
    documents=docs,
    ids=ids
)

print('chroma-db complete')
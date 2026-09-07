import streamlit as st
import os
from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from typing import List, TypedDict
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import START, StateGraph
from pathlib import Path

from openai_key import MISSING_KEY_MESSAGE, get_openai_key


st.set_page_config(page_title='LLM RAG', page_icon='🔎')

st.sidebar.header('LLM RAG 🔎')
st.title('🔎 LLM RAG Interface')


openai_api_key = get_openai_key()
model = st.sidebar.selectbox("Model", ["gpt-5-mini", "gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"])

if not openai_api_key:
    st.error(MISSING_KEY_MESSAGE)
else:
    os.environ["OPENAI_API_KEY"] = openai_api_key
    llm = init_chat_model(model, model_provider='openai')


    embeddings = OpenAIEmbeddings(model='text-embedding-3-large')

    vector_store = Chroma(
        collection_name='Etude_samples', # I forgot to change this name in chroma-db_creation so it has to stay now
        embedding_function=embeddings,
        # Relative to this file, not the working directory, so the app runs
        # correctly whichever directory streamlit is started from.
        persist_directory=str(Path(__file__).parent.parent / 'chroma-db')
    )


    class State(TypedDict):
        question: str
        context: List[Document]
        answer: str
        k: int

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Use only the information provided in the context below to answer the question. If the answer is not in the context, say 'The information is not available.'"),
        ("human", "Context:\n{context}\n\nQuestion: {question}")
    ])

    def retrieve(state: State):
        RAG_retrieved_docs = vector_store.similarity_search(state['question'], k=state['k'])
        return {"context": RAG_retrieved_docs}

    def generate(state: State):
        docs_str = '\n\n'.join([doc.page_content for doc in state['context']])
        message = prompt.invoke({"question": state["question"], "context": docs_str})
        response = llm.invoke(message)
        return {'answer': response.content}


    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, 'retrieve')
    graph = graph_builder.compile()


    with st.form("my_form"):
        question = st.text_area(
            "Enter question:",
            "Which pieces did Grainger use for teaching purposes?",
        )
        k = st.text_area(
            "Enter number of entries (1-50) to fetch from the catalogue:",
            '5',
        )
        submitted = st.form_submit_button("Submit")
        if not k.isdigit():
            st.warning('Please enter a number of documents to fetch.', icon='⚠')
        else: 
            k = int(k)
            if k < 1 or k > 50:
                st.warning('Please enter a number between 1-50.', icon='⚠')
            elif submitted:
                response = graph.invoke({
                    "question": question,
                    "k": k
                })
                st.info(response['answer'])
                st.info("The following are the entries fetched from _Grainger's Catalog of Music by Other Composers_:")
                for doc in response['context']:
                    st.info(doc.page_content)
"""Chroma retrieval with optional metadata filters (doc_type / department)."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.documents import Document

from stai.config import settings


@lru_cache(maxsize=1)
def get_vector_store():
    from langchain_chroma import Chroma
    from langchain_ollama import OllamaEmbeddings

    store = Chroma(
        collection_name=settings.collection_name,
        embedding_function=OllamaEmbeddings(
            model=settings.embed_model, base_url=settings.ollama_base_url
        ),
        persist_directory=str(settings.chroma_dir),
    )
    return store


def collection_count() -> int:
    return get_vector_store()._collection.count()


def retrieve(
    query: str,
    k: int | None = None,
    doc_type: str | None = None,
    department: str | None = None,
) -> list[Document]:
    """Top-k similarity search; empty list if the collection was never ingested."""
    store = get_vector_store()
    if collection_count() == 0:
        return []

    clauses = []
    if doc_type:
        clauses.append({"doc_type": {"$eq": doc_type}})
    if department:
        clauses.append({"department": {"$eq": department}})
    where = None
    if len(clauses) == 1:
        where = clauses[0]
    elif clauses:
        where = {"$and": clauses}

    return store.similarity_search(query, k=k or settings.retriever_k, filter=where)


def format_docs(docs: list[Document]) -> str:
    """Render retrieved chunks the way the agent is told to cite them."""
    blocks = []
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        blocks.append(f"[source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)

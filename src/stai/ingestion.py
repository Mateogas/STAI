"""Knowledge-base ingestion: data/hr_docs/*.md -> chunk -> embed -> Chroma.

Run with:  python -m stai.ingestion
Idempotent: the collection is reset and rebuilt on every run, so editing a
handbook doc and re-running is always safe.
"""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from stai.config import settings

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a markdown file into (front-matter dict, body).

    Front matter is a simple ``key: value`` block between ``---`` fences; we
    deliberately avoid a YAML dependency for three flat string fields.
    """
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, text[match.end():]


def load_documents(hr_docs_dir: Path | None = None) -> list[Document]:
    docs_dir = Path(hr_docs_dir or settings.hr_docs_dir)
    documents = []
    for path in sorted(docs_dir.glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        documents.append(
            Document(
                page_content=body.strip(),
                metadata={
                    "source": path.name,
                    "title": meta.get("title", path.stem),
                    "doc_type": meta.get("doc_type", "guide"),
                    "department": meta.get("department", "all"),
                },
            )
        )
    return documents


def split_documents(
    documents: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
    )
    return splitter.split_documents(documents)


def ingest() -> tuple[int, int]:
    """Rebuild the Chroma collection from the hr_docs folder.

    Imports are local so that pure-logic callers (and tests) of this module
    never need the embedding stack.
    """
    from langchain_chroma import Chroma
    from langchain_ollama import OllamaEmbeddings

    documents = load_documents()
    if not documents:
        raise FileNotFoundError(f"No .md docs found in {settings.hr_docs_dir}")
    chunks = split_documents(documents)

    store = Chroma(
        collection_name=settings.collection_name,
        embedding_function=OllamaEmbeddings(
            model=settings.embed_model, base_url=settings.ollama_base_url
        ),
        persist_directory=str(settings.chroma_dir),
    )
    store.reset_collection()
    store.add_documents(chunks)
    return len(documents), len(chunks)


def main() -> None:
    n_docs, n_chunks = ingest()
    print(
        f"Ingested {n_docs} docs -> {n_chunks} chunks into collection "
        f"'{settings.collection_name}' at {settings.chroma_dir}"
    )


if __name__ == "__main__":
    main()
